import tensorflow as tf


def fully_connected(x, in_n, out_n, module_cnt, init_weight=None, init_b=None):
    with tf.variable_scope("fc_%02d" % module_cnt):
        weight = tf.get_variable(
            "weight", None if init_weight is not None else [in_n, out_n], tf.float32,
            init_weight if init_weight is not None else tf.contrib.layers.xavier_initializer())
        bias = tf.get_variable(
            "bias", None if init_b else [out_n], tf.float32,
            init_b if init_b is not None else tf.zeros_initializer())
        return tf.nn.xw_plus_b(x, weight, bias)


def global_avg_pooling(x, keepdims=True):
    return tf.reduce_mean(x, [1, 2], keepdims=keepdims)


# chs in argument: avoid redundant variables in tf graph
#                  should do more in graph building phase; produces less garbage
# using pytorch batch_norm defaults
def batch_norm(
        x, chs, is_training, module_cnt, inference_only, eps=1e-5, momentum=.9,
        init_gamma=None, init_beta=None, init_r_mean=None, init_r_var=None):  # load from numpy
    with tf.variable_scope("bn_%02d" % module_cnt):
        gamma = tf.get_variable(
            "gamma", dtype=tf.float32,
            initializer=init_gamma if init_gamma is not None else tf.ones([chs]))
        beta = tf.get_variable(
            "beta", dtype=tf.float32,
            initializer=init_beta if init_beta is not None else tf.zeros([chs]))
        r_mean = tf.get_variable(
            "r_mean", dtype=tf.float32,
            initializer=init_r_mean if init_r_mean is not None else tf.zeros([chs]),
            trainable=False)
        r_var = tf.get_variable(
            "r_var", dtype=tf.float32,
            initializer=init_r_var if init_r_var is not None else tf.ones([chs]),
            trainable=False)
        # Avoid producing dirty graph
        if inference_only:
            x = tf.nn.batch_normalization(x, r_mean, r_var, beta, gamma, eps)
        else:
            def _train():
                mean, variance = tf.nn.moments(x, [0, 1, 2], name="moments")
                # not using tf.train.ExponentialMovingAverage for better variable control
                # so we can load trained variables into inference_only graph
                update_mean_op = tf.assign(
                    r_mean, r_mean * momentum + mean * (1 - momentum))
                update_var_op = tf.assign(
                    r_var, r_var * momentum + variance * (1 - momentum))
                with tf.control_dependencies([update_mean_op, update_var_op]):
                    return tf.nn.batch_normalization(x, mean, variance, beta, gamma, eps)
            x = tf.cond(
                is_training,
                _train,
                lambda: tf.nn.batch_normalization(x, r_mean, r_var, beta, gamma, eps))
        return x


def conv(
        x, in_chs, out_chs, k_size, stride, module_cnt, bias, pad=0,
        init_weight=None, init_b=None):  # load from numpy
    with tf.variable_scope("conv_%02d" % module_cnt):
        weight = tf.get_variable(
            "kernel",
            None if init_weight is not None else [k_size, k_size, in_chs, out_chs],
            tf.float32,
            init_weight if init_weight is not None else tf.contrib.layers.xavier_initializer())
        if pad > 0:
            x = tf.pad(x, [[0, 0], [pad, pad], [pad, pad], [0, 0]])
        x = tf.nn.conv2d(x, weight, [1, stride, stride, 1], "VALID")
        if bias:
            b = tf.get_variable(
                "bias", None if init_b is not None else [out_chs], tf.float32,
                init_b if init_b is not None else tf.zeros_initializer())
            x = tf.nn.bias_add(x, b)
        return x


def dwise_conv(
        x, in_chs, k_size, stride, module_cnt, bias, chs_mult=1, pad=0,
        init_weight=None, init_b=None):
    with tf.variable_scope("dwise_conv_%02d" % module_cnt):
        weight = tf.get_variable(
            "kernel",
            None if init_weight is not None else [k_size, k_size, in_chs, chs_mult],
            tf.float32,
            init_weight if init_weight is not None else tf.contrib.layers.xavier_initializer())
        if pad > 0:
            x = tf.pad(x, [[0, 0], [pad, pad], [pad, pad], [0, 0]])
        x = tf.nn.depthwise_conv2d(x, weight, [1, stride, stride, 1], "VALID")
        if bias:
            b = tf.get_variable(
                "bias", None if init_b else [int(in_chs * chs_mult)],
                tf.float32,
                init_b if init_b else tf.zeros_initializer())
            x = tf.nn.bias_add(x, b)
        return x


def channel_shuffle(x, groups, module_cnt):
    with tf.variable_scope("channel_shuffle_%02d" % module_cnt):
        _, h, w, c = x.shape.as_list()
        x = tf.reshape(x, [-1, h, w, groups, c // groups])
        x = tf.transpose(x, [0, 1, 2, 4, 3])
        x = tf.reshape(x, [-1, h, w, c])
        return x


def shufflenet_unit(
        x, in_c, is_training, module_cnt,
        inference_only, out_c=None, init_params=None):
    with tf.variable_scope("shufflenet_unit_%02d" % module_cnt):
        if out_c:  # Downsample and double (or more) the channels
            assert out_c >= in_c * 2
            chs = out_c // 2
            x1, x2 = x, x
            # 1st branch
            x1 = dwise_conv(
                x1, in_c, 3, 2, 0, False, 1, 1,
                init_params[0] if init_params else None)
            x1 = batch_norm(
                x1, in_c, is_training, 1, inference_only, 1e-5, .9,
                *init_params[1:5] if init_params else [None])
            x1 = conv(
                x1, in_c, chs, 1, 1, 2, False, 0,
                init_params[5] if init_params else None)
            x1 = batch_norm(
                x1, chs, is_training, 3, inference_only, 1e-5, .9,
                *init_params[6:10] if init_params else [None])
            # 2nd branch
            x2 = conv(
                x2, in_c, chs, 1, 1, 4, False, 0,
                init_params[10] if init_params else None)
            x2 = tf.nn.relu(batch_norm(
                x2, chs, is_training, 5, inference_only, 1e-5, .9,
                *init_params[11:15] if init_params else [None]))
            x2 = dwise_conv(
                x2, chs, 3, 2, 6, False, 1, 1,
                init_params[15] if init_params else None)
            x2 = batch_norm(
                x2, chs, is_training, 7, inference_only, 1e-5, .9,
                *init_params[16:20] if init_params else [None])
            x2 = conv(
                x2, chs, chs, 1, 1, 8, False, 0,
                init_params[20] if init_params else None)
            x2 = batch_norm(
                x2, chs, is_training, 9, inference_only, 1e-5, .9,
                *init_params[21:25] if init_params else [None])
            x = tf.nn.relu(tf.concat([x1, x2], 3))
        else:
            assert in_c % 2 == 0
            chs = in_c // 2
            left, right = x[..., :chs], x[..., chs:]
            right = conv(
                right, chs, chs, 1, 1, 0, False, 0,
                init_params[0] if init_params else None)  # no bias
            right = tf.nn.relu(batch_norm(
                right, chs, is_training, 1, inference_only, 1e-5, .9,
                *init_params[1:5] if init_params else [None]))
            right = dwise_conv(
                right, chs, 3, 1, 2, False, 1, 1,
                init_params[5] if init_params else None)
            right = batch_norm(
                right, chs, is_training, 3, inference_only, 1e-5, .9,
                *init_params[6:10] if init_params else [None])
            right = conv(
                right, chs, chs, 1, 1, 3, False, 0,
                init_params[10] if init_params else None)  # no bias
            right = tf.nn.relu(batch_norm(
                right, chs, is_training, 4, inference_only, 1e-5, .9,
                *init_params[11:15] if init_params else [None]))
            x = tf.concat([left, right], 3)
        return channel_shuffle(x, 2, 10 if out_c else 5)


class Net():

    def __init__(
            self, x, cls=2, alpha=1., input_size=(224, 224),
            inference_only=False, init_params=None, test_convert=False):
        # init_parmas is used when loading weight pretrained on other dataset(s), normally
        # imagenet, so the weights from the last fully connect layer should not be loaded
        assert len(input_size) == 2
        self.test_convert = test_convert
        self.output_neuron = cls if cls > 2 else 1
        self.x = x  # placeholder or data from tf.data.Dataset
        self.inference_only = inference_only
        # inference_only: so there's no need to feed is_training placholder on frozen graph
        #                 and hope graph optimization tool will fuse the constants.
        # if inference_only, self.is_training will never be used
        self.is_training = None if inference_only else tf.placeholder(tf.bool, name="is_training")
        self.input_size = (None, *input_size, 3)
        self.first_chs = 24
        self.last_chs = 2048 if alpha == 2. else 1024
        if alpha == 0.5:
            self.first_block_chs = 48
        elif alpha == 1.:
            self.first_block_chs = 116
        elif alpha == 1.5:
            self.first_block_chs = 176
        elif alpha == 2.:
            self.first_block_chs = 244
        else:
            import logging
            logging.error("Unexpected alpha, which should be 0.5, 1.0, 1.5, or 2.0")
            raise ValueError
        self.repeats = (3, 7, 3)
        self.out = self.build_net(init_params)

    def build_net(self, params):
        res = self.x
        res = conv(res, 3, self.first_chs, 3, 2, 0, False, 1,
                   params[0] if params is not None else None)
        res = batch_norm(
            res, self.first_chs, self.is_training, 1, self.inference_only, 1e-5, .9,
            *params[1:5] if params is not None else [None])
        res = tf.pad(tf.nn.relu(res), [[0, 0], [1, 1], [1, 1], [0, 0]])
        res = tf.nn.max_pool(res, [1, 3, 3, 1], [1, 2, 2, 1], "VALID")
        m_cnt = 2
        p_cnt = 5
        in_chs = self.first_chs
        out_chs = self.first_block_chs
        for repeat in self.repeats:
            res = shufflenet_unit(
                res, in_chs, self.is_training, m_cnt, self.inference_only, out_chs,
                params[p_cnt:p_cnt+25] if params is not None else None)
            m_cnt += 1
            p_cnt += 25
            in_chs = out_chs
            for _ in range(repeat):
                res = shufflenet_unit(
                    res, in_chs, self.is_training, m_cnt, self.inference_only, None,
                    params[p_cnt:p_cnt+15] if params is not None else None)
                m_cnt += 1
                p_cnt += 15
            out_chs *= 2
        # in_chs here is correct
        res = conv(
            res, in_chs, self.last_chs, 1, 1, m_cnt, False, 0,
            params[p_cnt] if params is not None else None)  # No bias
        m_cnt += 1
        p_cnt += 1
        res = tf.nn.relu(batch_norm(
            res, self.last_chs, self.is_training, m_cnt, self.inference_only, 1e-5, .9,
            *params[p_cnt:p_cnt+4] if params is not None else [None]))
        m_cnt += 1
        if not self.test_convert:
            res = tf.reshape(global_avg_pooling(res), [-1, self.last_chs])
            # not loading from params
            res = fully_connected(res, self.last_chs, self.output_neuron, m_cnt)
            if self.output_neuron == 1:  # used on binary classification
                res = tf.reshape(res, [-1])
        return res

    def save(self, path):
        pass

    def load(self, path):
        pass

    def load_from_numpy(self, path):
        pass

    def __call__(self, x):
        pass


def convert_pytorch_weight():

    import logging

    def p_load(net, sd):
        cnt = 0
        net_keys = list(net.state_dict().keys())
        net_keys = [k for k in net_keys if not k.endswith("num_batches_tracked")]
        for from_key, to_key in zip(sd.keys(), net_keys):
            net.state_dict()[to_key].copy_(sd[from_key])
            cnt += 1
        logging.info("%d params loaded" % cnt)

    import os
    import numpy as np
    import torch
    from shufflenet_v2_pytorch.shufflenetv2_base import shufflenetv2_base
    ar = np.random.rand(2, 224, 224, 3).astype(np.float32) * 10 - 5
    tnet = shufflenetv2_base()
    tar = torch.from_numpy(ar.transpose(0, 3, 1, 2))
    z = torch.load(os.path.join(
        "shufflenet_v2_pytorch", "shufflenetv2_x1_69.402_88.374.pth.tar"))
    # tnet.load_state_dict(z, strict=False)
    with torch.no_grad():
        p_load(tnet, z)
    params = []
    for k, v in z.items():
        v = v.numpy()
        assert v.ndim in [1, 2, 4], (k, v.ndim)
        if v.ndim == 4:
            if v.shape[1] == 1:
                v = v.transpose(2, 3, 0, 1)
            else:
                v = v.transpose(2, 3, 1, 0)
        params.append(v)
    inference_only = False
    is_training = True
    shape = [224, 224]
    a = tf.placeholder(tf.float32, shape=[None, *shape, 3])
    net = Net(a, inference_only=inference_only, init_params=params, test_convert=True)
    ab = net.out
    if inference_only or not is_training:
        tnet = tnet.eval()
    else:
        tnet = tnet.train()
    with torch.no_grad():
        tout = tnet(tar).numpy().transpose(0, 2, 3, 1)
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        z = sess.run(ab, {a: ar} if inference_only else {a: ar, net.is_training: is_training})
    diff = np.sqrt(np.mean((tout-z)**2))
    logging.info("Output diff between tensorflow and pytorch: %f" % diff)
    if diff > 1e-5:
        logging.warning(
            "Output diff between tensorflow and pytorch is bigger than 1e-5 (%f)" % diff)
    import pickle
    param_path = "imagenet_pretrained_shufflenetv2_1.0.pkl"
    with open(param_path, "wb") as f:
        pickle.dump(params, f)
    logging.info("Transposed numpy weights from pytorch model saved to %s" % param_path)


def _test():
    import numpy as np
    import logging
    shape = [2, 224, 224, 3]
    inference_only = False
    a = tf.placeholder(tf.float32, shape=[None, *shape[1:]])
    net = Net(a, inference_only=inference_only)
    ab = net.out
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        if inference_only:
            z = sess.run(ab, feed_dict={a: np.random.rand(*shape)})
        else:
            z = sess.run(ab, feed_dict={a: np.random.rand(*shape), net.is_training: True})
        logging.info(z.shape)


if __name__ == '__main__':
    convert_pytorch_weight()
