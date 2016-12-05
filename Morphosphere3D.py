"""
Morphspere 3D: analysis platform for lightsheet microscopy of organoids
@authors: Fanny Georgi, Vardan Andriasyan, Artur Yakimovich

"""

import skimage
import math
import cv2
from scipy import ndimage
from skimage import measure,morphology
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from ggplot import *
from PIL import Image
import re
#import multiproessing


def processGrayImage(inputImage):
    processedImage = (inputImage*255).astype('uint8')
    processedImage = np.asarray(processedImage)
    return processedImage
    
def processBinaryImage(inputImage, dilationDisk):
    selem = skimage.morphology.disk(dilationDisk)
    processedImage = cv2.dilate(inputImage,selem,iterations = 1)
    processedImage = ndimage.binary_fill_holes(processedImage)
    return processedImage
    
def thresholdImage(inputImage, gaussianSigma):
    blur = cv2.GaussianBlur(inputImage,(gaussianSigma,gaussianSigma),0)
    threshold, thresholdedImage = cv2.threshold(blur,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    return thresholdedImage

def visualizeMatrix(inputImage):
    if inputImage.dtype == 'bool':
        inputImage = inputImage.astype(int) * 255

    plt.imshow(inputImage, 'gray')
    plt.set_cmap('gray')
    plt.axis('on')
    plt.show()

def visualizeSaveMatrix(inputImage, stepName):
    if inputImage.dtype == 'bool':
        inputImage = inputImage.astype(int)*255
    
    plt.imshow(inputImage, 'gray')
    plt.set_cmap('gray')
    plt.axis('on')
    plt.show()
    im = Image.fromarray(inputImage)
    im.save(stepName)

def plotRDF(rdf, fileName):
    plot = ggplot(aes(x='r',y='IntensityNuclei'), data=rdf) + \
        geom_point(color= 'steelblue')
    print plot
    plot.save(fileName[:-4] + '_Nuclei_RDF.png')

    plot = ggplot(aes(x='r',y='IntensityVirus'), data=rdf) + \
        geom_point(color= '#33CC33')
    print plot
    plot.save(fileName[:-4] + '_Virus_RDF.png')

# combining two datasets in one plot does not work yet although claimed otherwise
# alterantively, combine both datasets into one and print as facet_grid
# def plotRDF(rdfNuclei, fileNameNuclei, rdfVirus, fileNameVirus):
#     ##### ##### ##### To do: plot in same graph, axis labels, x axis in um, y min 0
#     rdfPlot = ggplot(aes(x = 'r', y = 'Intensity'), data = rdfNuclei) + \
#               geom_point('steelblue') + \
#               geom_point(x = 'r', y = 'Intensity', data = rdfVirus, color = '#33CC33')
#     print rdfPlot
#     rdfPlot.save(fileNameVirus[:-4] + '_RDF.png')

def label2mask(labeledImage,label):
    labeledImage[labeledImage!=label] = 0
    labeledImage[labeledImage==label] = 1
    return labeledImage
    #for unique_counts(labeledImage)
    
def cartesian2Polar(x,y):
    r = math.sqrt(np.square(x)+np.square(y))
    phi = math.atan2(x,y)
    return r, phi

def cartesian2Spheric(x,y,z):
    r = math.sqrt(np.square(x)+np.square(y)+np.square(z))
    theta = math.atan2(y,x)
    phi = math.acos(z/r)
    return r, theta, phi
    
def recenterCertesian(centroid,x,y,z=False):
    if z == False:
        xCentroid,yCentroid = centroid
        x = x-xCentroid
        y = y-yCentroid
        return x, y
    else:
        xCentroid,yCentroid,zCentroid = centroid
        x = x-xCentroid
        y = y-yCentroid
        z = z-zCentroid
        return x, y, z
        
def computeRDF(inputImageNuclei, inputImgeVirus, centroid, diameter, numberOfBins):
    n,m = np.shape(inputImageNuclei)
    # preallocate matrix for r values
    rValues = np.zeros((n,m))
    columns = ['r','IntensityNuclei', 'IntensityVirus']
    rdf = pd.DataFrame(columns=columns)
    
    for iN in range(0,n):
        vecM = np.arange(m)
        x,y = recenterCertesian(centroid,iN,vecM)
        vecCartesian2Polar = np.vectorize(cartesian2Polar)
        r, phi = vecCartesian2Polar(x, y)
        #r, phi = cartesian2Polar(x,y)
        rValues[iN,vecM] = r

    # convert intensities and r matrices to 1D arrays for speed
    rValuesVect = rValues.ravel()
    inputImageNucleiVect = inputImageNuclei.ravel()
    inputImageVirusVect = inputImageVirus.ravel()
    
    if numberOfBins == 'max':
        steps = 1
        values = np.unique(rValuesVect)
    else:
        steps = np.floor((diameter/2)%numberOfBins)
        values = np.arange(steps,diameter/2,steps)
    # calculate RDF as np. e.g. sum / mean / median / SD / .... optimal need to be evaluated
    for iRvalue in values:
        iIntensityNuclei = np.mean(inputImageNucleiVect[np.where(rValuesVect[np.logical_and(rValuesVect >= iRvalue-steps,rValuesVect <= iRvalue)])])
        iIntensityVirus = np.mean(inputImageVirusVect[np.where(rValuesVect[np.logical_and(rValuesVect >= iRvalue - steps, rValuesVect <= iRvalue)])])
        iRDF = pd.DataFrame({'r': [iRvalue], 'IntensityNuclei': [iIntensityNuclei], 'IntensityVirus': [iIntensityVirus]})
        rdf = rdf.append(iRDF)
    return rdf.sort('r')
    
def getCentralRegionAndProperties(labeledImage, imageHeight, imageWidth):
    allProperties = measure.regionprops(labeledImage)
    ################## initialize empty arrays for area and distance filtering
    areas=np.empty(len(allProperties))
    distancesToCenter = np.empty(len(allProperties))
    labels = np.empty(len(allProperties))
    
    ################## find the index connected area which is closest to center of the image also area filter
    i = 0
    for props in allProperties:
        y0, x0 = props.centroid
        distance = math.sqrt((y0 -imageHeight/2)**2 + (x0 -imageWidth/2)**2)
        distancesToCenter[i] = distance
        areas[i] = props.area
        labels[i] = props.label
        i=i+1
    
    ################## filter by area
    distancesToCenter = distancesToCenter[areas>minSpheroidArea]
    labels = labels[areas>minSpheroidArea]
    ################## filter by distance and get the index
    indexOfMinDistance = labels[distancesToCenter == min(distancesToCenter)]
    indexOfMinDistance = indexOfMinDistance.astype(int) -1
    
    #selectedCC = (labeledImage == allProperties[indexOfMinDistance].label)
    
    #spheroidBWImage = selectedCC.astype("uint8")
    
    ### actually not neccassary
    boundingBox =  allProperties[indexOfMinDistance].bbox
    
    label = allProperties[indexOfMinDistance].label
    centroid = allProperties[indexOfMinDistance].centroid
    perimeter = allProperties[indexOfMinDistance].perimeter
    area = allProperties[indexOfMinDistance].area
    diameter = allProperties[indexOfMinDistance].equivalent_diameter
    majorAxis = allProperties[indexOfMinDistance].major_axis_length
    minorAxis = allProperties[indexOfMinDistance].minor_axis_length
    circularity = 4*math.pi*(area/perimeter**2)
    
    return label, centroid, perimeter, area, diameter, majorAxis, minorAxis, circularity, boundingBox


################## open single z plane from 16bit image
fileNameNuclei = 'B01_405_z720.tif'
fileNameVirus = 'B01_488_z720.tif'
inputImageNuclei = cv2.imread(fileNameNuclei, -1) #0 = grey, 1=RGB, -1=unchanged
inputImageVirus = cv2.imread(fileNameVirus, -1) #0 = grey, 1=RGB, -1=unchanged

################## validate input visually
visualizeMatrix(inputImageNuclei)
visualizeMatrix(inputImageVirus)

################## convert input image to 8bit
processedImageNuclei = processGrayImage(inputImageNuclei)
processedImageVirus = processGrayImage(inputImageVirus)

################## smoothen and threshold input image
gaussianSigma = 5
thresholdedImageNuclei = thresholdImage(processedImageNuclei, gaussianSigma)

################## segment shperoid area
minSpheroidArea = 500
dilationDisk = 100
blockSize = 501

processedBinaryImage = processBinaryImage(thresholdedImageNuclei, dilationDisk)
stepNameBinaryNuclei = fileNameNuclei[:-4] + '_processedBinaryImageNuclei' + '.tif'
visualizeSaveMatrix(processedBinaryImage, stepNameBinaryNuclei)

################## calculate center of spheroid
imageHeight, imageWidth = inputImageNuclei.shape[:2]
labeledImageNuclei = measure.label(thresholdedImageNuclei)
getCentralRegionAndProperties(labeledImageNuclei, imageHeight, imageWidth)
label, centroid, perimeter, area, diameter, majorAxis, minorAxis, circularity, boundingBox = getCentralRegionAndProperties(labeledImageNuclei, imageHeight, imageWidth)

labeled2mask = label2mask(labeledImageNuclei,label)
maskedImageNuclei = np.multiply(inputImageNuclei, labeled2mask)
maskedImageVirus = np.multiply(inputImageVirus,labeled2mask)

stepNameMaskedNuclei = fileNameNuclei[:-4] + '_maskedImageNuclei' + '.tif'
visualizeSaveMatrix(maskedImageNuclei, stepNameMaskedNuclei)
stepNameMaskedVirus = fileNameVirus[:-4] + '_maskedImageVirus' + '.tif'
visualizeSaveMatrix(maskedImageVirus, stepNameMaskedVirus)

numberOfProcesses = 4
#pool = multiprocessing.Pool(processes=numberOfProcesses)
#maskedImageRDF = pool.map(computeRDF, inputImage, centroid)
#pool.close()
#pool.join()

################## calculate radial distribution function
numberOfBins = 5 # numberOfBins = max for single pixel resolution
maskedImageRDF = computeRDF(inputImageNuclei,inputImageVirus, centroid, diameter, numberOfBins)

################## plot RDFs
plotRDF(maskedImageRDF, fileNameNuclei)

################## calculate radial distribution function
maskedImageRDF.to_csv(fileNameNuclei[:-4] + '_RDF.csv', sep=',')

print 'Ran MorphoSphere3D for ' + fileNameNuclei[:-4]