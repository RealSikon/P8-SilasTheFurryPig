#Code modified from: https://github.com/wannabeOG/ExpertNet-Pytorch 

#!/usr/bin/env python
# coding: utf-8

"""
This module tests the "experts" that have been generated by the generate_models.py file. If the wrong autoencoder were to be 
selected, the performance would obviously suffer. A metric to determine how many times this occurs has been designed. Since in 
these tasks. 

"""
import torch
torch.backends.cudnn.benchmark=True

import torch.nn as nn
from torch.autograd import Variable
import torch.optim as optim
import torch.nn.functional as F

import torchvision.datasets as datasets
import torchvision.models as models
import torchvision.transforms as transforms

import argparse 
import numpy as np
from random import shuffle
import os

import copy
from autoencoder import *

import sys
sys.path.append(os.path.join(os.getcwd(), 'utils'))
from tqdm import tqdm

from encoder_train import *
from encoder_utils import *

from model_train import *
from model_utils import *

def test_models(args):
	use_gpu = args.use_gpu  and torch.cuda.is_available()
	batch_size = args.batch_size
	
	new_path = os.path.join(os.getcwd(), "models", "autoencoders")
	num_ae = len(next(os.walk(new_path))[1])
	task_number_list = [x for x in range(1,num_ae+1)]
	#shuffle(task_number_list)

	classes = []

	#transformations for the test data
	data_transforms_tin = {
		'test': transforms.Compose([
			transforms.Resize(256),
			transforms.CenterCrop(224),
			transforms.ToTensor(),
			transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
		])
	}

	#transforms for the mnist dataset. Applicable for the tasks 5-9
	data_transforms_mnist = {
		'test': transforms.Compose([
				transforms.Resize(256),
				transforms.CenterCrop(224),
				transforms.ToTensor(),
				transforms.Normalize([0.1307,], [0.3081,])
		])
	}


	#get the paths to the data and model
	data_path = os.path.join(os.getcwd(), "Data")
	encoder_path = os.path.join(os.getcwd(), "models", "autoencoders")
	model_path = os.path.join(os.getcwd(), "models", "trained_models")


	#Get the number of classes in each of the given task folders
	for task_number in task_number_list:

		path_task = os.path.join(data_path, "Task_" + str(task_number))
		if(task_number <=4):
			#get the image folder
			image_folder = datasets.ImageFolder(os.path.join(path_task, 'test'), transform = data_transforms_tin['test'])
			classes.append(len(image_folder.classes))

		else:
			image_folder = datasets.ImageFolder(os.path.join(path_task, 'test'), transform = data_transforms_mnist['test'])
			classes.append(len(image_folder.classes))


	#shuffle the sequence of the tasks
	#print("Shuffling tasks")
	#shuffle(task_number_list)

	#set the device to be used and initialize the feature extractor to feed the data into the autoencoder
	device = torch.device("cuda:0" if torch.cuda.is_available() and use_gpu else "cpu")
	feature_extractor = Alexnet_FE(models.alexnet(pretrained=True))
	feature_extractor.to(device)

	for task_number in task_number_list:
		print("Testing task " + str(task_number))

		#get the paths to the data and model
		path_task = os.path.join(data_path, "Task_" + str(task_number))

		if(task_number >=1 and task_number <=4):
			#get the image folder
			image_folder = datasets.ImageFolder(os.path.join(path_task, 'test'), transform = data_transforms_tin['test'])
			dset_size = len(image_folder)

		else:
			#get the image folder
			image_folder = datasets.ImageFolder(os.path.join(path_task, 'test'), transform = data_transforms_mnist['test'])
			dset_size = len(image_folder)

	
		dset_loaders = torch.utils.data.DataLoader(image_folder, batch_size = batch_size,
														shuffle=True, num_workers=2)

		best_loss = 99999999999
		model_number = 0

		
		#Load autoencoder models for tasks 1-9; need to select the best performing autoencoder model
		for ae_number in task_number_list:
			print()
			print("Autoencoder no. " + str(ae_number))
			ae_path = os.path.join(encoder_path, "autoencoder_" + str(ae_number))
			
			#Load a trained autoencoder model
			model = Autoencoder()
			model.load_state_dict(torch.load(os.path.join(ae_path, 'best_performing_model.pth')))

			running_loss = 0
			model.to(device)

			#Test out the different auto encoder models and check their reconstruction error
			for data in tqdm(dset_loaders):
				input_data, labels = data



				if (use_gpu):
					input_data = input_data.to(device)
				
				else:
					input_data  = Variable(input_data)


				#get the input to the autoencoder from the conv backbone of the Alexnet
				input_to_ae = feature_extractor(input_data)
				input_to_ae = input_to_ae.view(input_to_ae.size(0), -1)

				input_to_ae = F.sigmoid(input_to_ae)
			
				#get the outputs from the model
				preds = model(input_to_ae)
				loss = encoder_criterion(preds, input_to_ae)
		




				running_loss = running_loss + loss.item()

			model_loss = running_loss/dset_size

			if(model_loss < best_loss):
				best_loss = model_loss
				model_number = ae_number
		



		if(model_number == task_number):
			print ("\nThe correct autoencoder has been found")

		else:
			print ("\nIncorrect routing, wrong model has been selected (selected model " + str(model_number) + ")")


		#Load the expert that has been found by this procedure into memory
		trained_model_path = os.path.join(model_path, "model_" + str(model_number))

		#Get the number of classes that this expert was exposed to
		file_name = os.path.join(trained_model_path, "classes.txt") 
		file_object = open(file_name, 'r')

		num_of_classes = file_object.read()
		file_object.close()

		num_of_classes = int(num_of_classes)

		model = GeneralModelClass(num_of_classes)
		model.load_state_dict(torch.load(os.path.join(trained_model_path, 'best_performing_model.pth')))

		#initialize the results statistics
		running_loss = 0
		running_corrects = 0

		#run the test loop over the model
		print("Model test")
		for data in tqdm(dset_loaders):
			input_data, labels = data


			if (use_gpu):
				input_data = Variable(input_data.to(device))
				labels = Variable(labels.to(device)) 
		
			else:
				input_data  = Variable(input_data)
				labels = Variable(labels)
		
			model.to(device)

			outputs = model(input_data)

		
			#(currently not functional) for a more robust analysis check over the entire output layer (similar to multi head setting)
			#_, preds = torch.max(outputs, 1
			#loss = model_criterion(outputs, labels, 'CE')

			#check over only the specific layer identified by the AE (similar to single head setting)
			_, preds = torch.max(outputs[:, -classes[model_number-1]:], 1)
			fitted_outputs = torch.zeros(outputs.shape[0], classes[task_number], dtype=outputs.dtype, device=outputs.device)
			fitted_outputs[:, -classes[model_number-1]:] = outputs[:, -classes[model_number-1]:]
			loss = model_criterion(fitted_outputs, labels, args, flag = 'CE')
			
			running_corrects += torch.sum(preds==labels.data)
			running_loss = running_loss + loss.item()





		model_loss = running_loss/dset_size
		model_accuracy = running_corrects.double()/dset_size
		print("\nModel accuracy: " + str(model_accuracy))

		#Store the results into a file
		with open("results.txt", "a") as myfile:
			myfile.write("\n{}: {}".format(task_number, model_accuracy*100))
			myfile.close()









