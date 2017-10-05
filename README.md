# Cat-recognition-app
A cloud-based machine learning (ML) application recognize cats in pictures.

This repository contain all the necessary python code required to build a ML application
and deploy it on the AWS.

## Demo




## Introduction
Although there are already lots of good tutorials telling you how to build a machine learning model, 
I feel that there is little explanation about how to actually deploy your model as a web application.

So I decided to build a simple image classifier
that is able to recognize cats and deploy it using AWS Lambda in order to simulate(or at least practice) 
how to actually deploy a ML model in real world.
 


## Steps to follow
- Build environment (on mac)
- Train a Convoluational Neural Network(CNN)
- Deploy trained model



## Build environment (on mac)
Use python 3.6 to ensure that we can deploy our model on AWS Lambda later.
```commandline
pyenv install 3.6.1
```

Create a new virtual environment to manage dependencies 
and use the env under current project folder.
```commandline
pyenv virtualenv 3.6.1 py3.6-ml-app
cd cat-recognition-app/
pyenv local py3.6-ml-app
```

Install libraries for training models and visualization.
We will train our models using TensorFlow on jupyter notebook.
```commandline
pip install numpy tensorflow jupyter matplotlib seaborn tqdm
```

In case you also want to use jupyter notebook extensions:
```commandline
pip install jupyter_contrib_nbextensions
```

## Train a Convoluational Neural Network

All the code for building the model will be included in this [notebook](cat_recognizer.ipynb). 
To actually execute code in the notebook, start a jupyter server:

```commandline
jupyter notebook
```





## Miscellaneous
- [pyenv build fail](https://github.com/pyenv/pyenv/issues/655): Try install CLI dev tools
```commandline
xcode-select --install
```












