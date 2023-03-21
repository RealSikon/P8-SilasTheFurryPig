print("come here piggy piggy")

# imports
import torch
import torch.nn as nn
import argparse
import os
import pathlib
import datetime 
from datetime import datetime
from tqdm import tqdm

import torchvision.datasets as datasets
import torchvision.models as models
import torchvision.transforms as transforms

from autoencoder import Autoencoder, Alexnet_FE
from encoder_train import *
from initial_model_train import *

parser = argparse.ArgumentParser()
parser.add_argument("--lr",         type=float, default=0.0002, help="Learning rate")
parser.add_argument("--batch_size", type=int,   default=64,     help="Size of the batches")
parser.add_argument("--latent_dim", type=int,   default=64,     help="Dimensionality of the latent space")
#tuning not explicitly implemented
parser.add_argument('--num_epochs_encoder', default=15, type=int, help='Number of epochs you want the encoder model to train on')
parser.add_argument('--num_epochs_model', default=40, type=int, help='Number of epochs you want  model to train on')
#tuning not implemented for these
parser.add_argument("--beta1",      type=float, default=0.5,    help="Beta1 hyperparameter for Adam optimizer")
parser.add_argument("--no_of_tasks",      type=float, default=9,    help="Number of tasks")
parser.add_argument("--dataset_boundaries",      type=list, default=[4,9],    help="Final task index for each dataset")

# General options
parser.add_argument("--dataset",			type=str,	default="FB15K237",	help="Which dataset folder to use as input")
parser.add_argument("--mode",				type=str,	default="test",	help="Which thing to do, overall (run/test/tune/dataTest)")
#"Booleans"
parser.add_argument("--use_gpu",			type=str,	default="True",	help="Use GPU for training (when without raytune)? (cuda)")

# Output options 
parser.add_argument("--sample_interval",	type=int,  default=5000,    help="Iters between image samples")
parser.add_argument("--tqdm_columns",		type=int,  default=60,    help="Total text columns for tqdm loading bars")

opt = parser.parse_args()

#convert "Booleans" to actual bools
if opt.use_gpu == "False":
	opt.use_gpu = False
else:
	opt.use_gpu = True

print(opt)


# --- setup ---
# Dataset directory
def path_join(p1, p2):
	return os.path.join(p1, p2)

workDir  = pathlib.Path().resolve()
dataDir  = path_join(workDir.parent.resolve(), 'datasets')
inDataDir = path_join(dataDir, opt.dataset)
loss_graphDir = path_join(dataDir, "_loss_graph")
if not os.path.exists(loss_graphDir):
	os.makedirs(loss_graphDir)

# filepath for storing loss graph
graphDirAndName = path_join(loss_graphDir, "loss_graph.png")


# Seed
seed = torch.Generator().seed()
print("Current seed: " + str(seed))

# Computing device
cuda = opt.use_gpu and torch.cuda.is_available()
device = 'cpu'
if cuda: device = 'cuda:0'


#transforms for the tiny-imagenet dataset. Applicable for the tasks 1-4
data_transforms_tin = {
		'train': transforms.Compose([
			transforms.Resize(256),
			transforms.CenterCrop(224),
			transforms.ToTensor(),
			transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
		]),
		'test': transforms.Compose([
			transforms.Resize(256),
			transforms.CenterCrop(224),
			transforms.ToTensor(),
			transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
		])
	}


#transforms for the mnist dataset. Applicable for the tasks 5-9
data_transforms_mnist = {
	'train': transforms.Compose([
			transforms.ToTensor(),
			transforms.Normalize([0.1307,], [0.3081,])
		]),
		'test': transforms.Compose([
			transforms.ToTensor(),
			transforms.Normalize([0.1307,], [0.3081,])
		])
}


#Initial model 
pretrained_alexnet = models.alexnet(pretrained = True)

#Derives a feature extractor model from the Alexnet model
feature_extractor = Alexnet_FE(pretrained_alexnet)


for task_number in range(1, opt.no_of_tasks+1):
	
	print ("Task Number {}".format(task_number))
	data_path = os.getcwd() + "/Data"
	encoder_path = os.getcwd() + "/models/autoencoders"
	#model_path = os.getcwd() + "/models/trained_models"

	path_task = data_path + "/Task_" + str(task_number)
	
	if (task_number <= opt.dataset_boundaries[0]):
		image_folder = datasets.ImageFolder(path_task + "/" + 'train', transform = data_transforms_tin['train'])
	else:
		image_folder = datasets.ImageFolder(path_task + "/" + 'train', transform = data_transforms_mnist['train'])	
	
	dset_size = len(image_folder)

	device = torch.device("cuda:0" if opt.use_gpu else "cpu")

	dset_loaders = torch.utils.data.DataLoader(image_folder, batch_size = opt.batch_size,
													shuffle=True, num_workers=4)

	mypath = encoder_path + "/autoencoder_" + str(task_number)

	if os.path.isdir(mypath):
		############ check for the latest checkpoint file in the autoencoder ################
		onlyfiles = [f for f in os.listdir(mypath) if os.path.isfile(os.path.join(mypath, f))]
		max_train = -1
		flag = False

		model = Autoencoder(256*13*13)
		
		store_path = mypath
		
		for file in onlyfiles:
			if(file.endswith('pth.tr')):
				flag = True
				test_epoch = int(file[0])
				if(test_epoch > max_train): 
					max_epoch = test_epoch
					checkpoint_file_encoder = file
		#######################################################################################
		
		if (flag == False): 
			checkpoint_file_encoder = ""

	else:
		checkpoint_file_encoder = ""

	#get an autoencoder model and the path where the autoencoder model would be stored
	model, store_path = add_autoencoder(256*13*13, 100, task_number)

	#Define an optimizer for this model 
	optimizer_encoder = optim.Adam(model.parameters(), lr = 0.003, weight_decay= 0.0001)

	print ("Reached here for {}".format(task_number))
	print ()
	#Training the autoencoder
	autoencoder_train(model, feature_extractor, store_path, optimizer_encoder, encoder_criterion, dset_loaders, dset_size, opt.num_epochs_encoder, checkpoint_file_encoder, opt.use_gpu)

	#Train the model
	if(task_number == 1):
		train_model_1(len(image_folder.classes), feature_extractor, encoder_criterion, dset_loaders, dset_size, opt.num_epochs_model , True, task_number,  lr = opt.lr)
	else:	
		train_model(len(image_folder.classes), feature_extractor, encoder_criterion, dset_loaders, dset_size, opt.num_epochs_model , True, task_number,  lr = opt.lr)