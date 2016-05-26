# Run the algorithm using prepared data from a database
# Specifically designed to run Smart* Data
# Filename:     algoRun.py
# Author:       mjmor, dvorva, apadin
# Start Date:   ??? before 4/30/2016

print "Welcome to algoRun"

################################################################################

print "Preparing libraries..."

import time
import datetime as dt
import random

import grapher
from database import Database

import json
from urllib import urlopen

import numpy as np
import scipy as sp
import scipy.stats
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import date

from tf_functions import tf_train

from algoRunFunctions import movingAverage
from algoRunFunctions import train
from algoRunFunctions import runnable
from algoRunFunctions import severityMetric

from sklearn.metrics import recall_score
from sklearn.metrics import precision_score
from sklearn.metrics import f1_score

import mysql.connector

################################################################################

print "Loading configuration settings..."

y_predictions = []
y_target = []
y_time = []
w_opt = []
a_opt = 0
b_opt = 0
rowCount = 0
initTraining = False
notRunnableCount = 0
mu = 0; sigma = 1000
w, L = (.84, 3.719) # EWMA parameters. Other pairs can also be used, see paper
Sn_1 = 0
p_array = []

# Initialize database
database = Database()

print "Reading configuration files..."
with open('smartDriver.json') as data_file:
    jsonDataFile = json.load(data_file)

#Period: length of forecasting window, in hours
#Granularity: time between data, in minutes
matrixLength = int(jsonDataFile["windowSize"])*60/int(jsonDataFile["granularity"])
forecastingInterval = int(jsonDataFile["forecastingInterval"])*60/int(jsonDataFile["granularity"])

inputIDs = jsonDataFile["idSelection"]
inputIDs = inputIDs.split(',')
idArray = []
#Create a list of ID numbers, given input.
#interprets 1-3 to include 1,2,3.
for selection in inputIDs:
    if '-' not in selection:
        idArray.append(int(selection))
    else:
        bounds = selection.split('-')
        for index in range(int(bounds[0]), int(bounds[1])+1):
            idArray.append(index)

#Remove duplicates:
idArray = list(set(idArray))

#Sort the list.
idArray.sort()

#Fill columns with the corresponding column, given IDarray.
#Invariant: the ID in idArray at a given index should correspond
#           to the columnName at the same index in the column list.
startTimeList = []
endTimeList = []
columns = []
lastData = [] #Data point of last valid timestamp - init garbage
lastDataTime = [] #Timestamp of last valid timestamp - init very old [TODO]
shouldBeRounded = []
countNoData = [] #fordebug
severityArray = []
for sensorID in idArray:
    if "circuit" in jsonDataFile["data"][sensorID-1]["columnName"]:
        shouldBeRounded.append(1)
    else:
        shouldBeRounded.append(0)
    columns.append(jsonDataFile["data"][sensorID-1]["columnName"])
    startTimeList.append(jsonDataFile["data"][sensorID-1]["startTime"])
    endTimeList.append(jsonDataFile["data"][sensorID-1]["endTime"])
    lastDataTime.append(dt.datetime.min)
    lastData.append(-1)
    countNoData.append(0) #fordebug

countNoData.append(0) #fordebug


#Add total energy consumption column:
columns.append(jsonDataFile["totalConsum"]);
lastData.append(-1)
shouldBeRounded.append(1)
lastDataTime.append(dt.datetime.min)

#Find latest start time, earliest end time.
startTime = dt.datetime.strptime(max(startTimeList), "%Y-%m-%d %H:%M:%S")
endTime = dt.datetime.strptime(min(endTimeList), "%Y-%m-%d %H:%M:%S")

if(int(jsonDataFile["specifyTime"])):
   startTime = dt.datetime.strptime(jsonDataFile["beginTime"], "%Y-%m-%d %H:%M:%S")
   endTime = dt.datetime.strptime(jsonDataFile["endTime"], "%Y-%m-%d %H:%M:%S")

granularityInSeconds = int(jsonDataFile["granularity"])*60

#X window init.
X =  np.zeros([matrixLength, len(columns)], np.float32)
y = [None]*matrixLength

################################################################################

print "Beginning analysis..."

while startTime < endTime:

    currentRow = rowCount % matrixLength

    # Train if we have collected enough data
    if(rowCount % forecastingInterval == 0 and rowCount >= matrixLength):

        data = X[:, :len(columns)-1]
        y = X[:, len(columns)-1]

        if(initTraining or runnable(data) > 0.5):

            # For BLR train
            #w_opt, a_opt, b_opt, S_N = train(data, y)

            # For TF train            
            w_opt, a_opt, b_opt, S_N = tf_train(data, y)
            initTraining = True

        else:
            notRunnableCount += 1
            if(notRunnableCount > 5):
                print "Data not runnable too many times! Exiting..."

    
    #Some of the data seems bad on the 31st - too many NULLS
    if startTime > dt.datetime(2012, 5, 30) and startTime < dt.datetime(2012, 6, 1):
        startTime = dt.datetime(2012, 6, 1)

    if(rowCount % 240 == 0):
        print "trying time: %s " % startTime

    # Query for new data
    line = database.get_avg_data(startTime, startTime + dt.timedelta(0,granularityInSeconds), columns)
    
    for i in range(0, len(columns)):
       
        #We have new valid data! Also update lastData
        if line[i] > 0:
            X[currentRow, i] = line[i]
            lastData[i] = line[i]
            lastDataTime[i] = startTime

        #No new data.
        else:
            #X[currentRow, i] = lastData[i]
            X[currentRow, i] = 0
            countNoData[i] += 1
    
    # Make prediction:
    if initTraining:

        # Prediction is dot product of x_n and weight matrix
        x_n = X[currentRow, :-1]
        prediction = max(0.0, np.inner(w_opt,x_n)[0])

        y_predictions.append(prediction)
        y_target.append(X[currentRow, -1])
        y_time.append(startTime)
        
        error = y_predictions[-1] - y_target[-1]
        sigma = np.sqrt(1/b_opt + np.dot(np.transpose(x_n),np.dot(S_N, x_n)))

        # Catching pathogenic cases where variance (ie, sigma) gets too small
        if sigma < 1:
            sigma = 1

        # Update severity metric
        mu = mu; sigma = sigma
        Sn, Zn = severityMetric(error, mu, sigma, w, Sn_1)
        severityArray.append(Sn)
        #Zscore_array[n] = Zn
        Sn_1 = Sn
        p = 1 - sp.stats.norm.cdf(error, mu, sigma)
        p_array.append(p)

    # No prediction made
    else:
        severityArray.append(0)

    #Increment and loop
    startTime += dt.timedelta(0,granularityInSeconds)
    rowCount += 1

    # Pickle the data for later graphing
    if(rowCount % forecastingInterval == 0 and initTraining):
        grapher.write_csv(y_target, y_predictions, y_time)


################################################################################

print "Analysis complete."
print "Graphing and statistics..."

# Hereafter is just result reporting and graphing
# Prediction accuracy
n_samples = rowCount-1
training = int(jsonDataFile["windowSize"])*(60 / int(jsonDataFile["granularity"])) #init prediction period.
T = n_samples-training #prediction length
smoothing_win = 120
y_target = np.asarray(y_target)
y_predictions = np.asarray(y_predictions)
y_target_smoothed = movingAverage(y_target, smoothing_win)
y_predictions_smoothed = movingAverage(y_predictions, smoothing_win)
rmse_smoothed = []
rmse = []
Re_mse = []
smse = []
co95 = []

# Prediction Mean Squared Error (smooth values)

PMSE_score_smoothed = np.linalg.norm(y_target_smoothed-y_predictions_smoothed)**2 / T
# Prediction Mean Squared Error (raw values)
PMSE_score = np.linalg.norm(y_target - y_predictions)**2 / T

confidence = 1.96 / np.sqrt(T) *  np.std(np.abs(y_target-y_predictions))
# Relative Squared Error
Re_MSE = np.linalg.norm(y_target-y_predictions)**2 / np.linalg.norm(y_target)**2
# Standardise Mean Squared Error
SMSE =  np.linalg.norm(y_target-y_predictions)**2 / T / np.var(y_target)

rmse_smoothed.append(np.sqrt(PMSE_score_smoothed))
rmse.append(np.sqrt(PMSE_score))
co95.append(confidence)
Re_mse.append(Re_MSE)
smse.append(SMSE)


print "No data counts:"
print countNoData

print "PMSE for smoothed: %d" % (PMSE_score_smoothed)
print "PMSE for nonsmoothed: %d" % (PMSE_score)
print "-------------------------------------------------------------------------------------------------"
print "%20s |%20s |%25s |%20s" % ("RMSE-score (smoothed)", "RMSE-score (raw)", "Relative MSE", "SMSE")
print "%20.2f  |%20.2f |%25.2f |%20.2f " % (np.mean(np.asarray(rmse_smoothed)), np.mean(np.asarray(rmse)), np.mean(np.asarray(Re_mse)), np.mean(np.asarray(smse)))
print "-------------------------------------------------------------------------------------------------"

OBSERVS_PER_HR = 60 / int(jsonDataFile["granularity"])
axescolor  = '#f6f6f6'  # the axes background color
distance = n_samples//5
tick_pos = [t for t in range(distance,n_samples,distance)]
tick_labels = [y_time[t] for t in tick_pos]
GRAY = '#666666'

plt.rc('axes', grid=False)
plt.rc('grid', color='0.75', linestyle='-', linewidth=0.5)
textsize = 9
left, width = 0.1, 0.8
rect1 = [left, 0.7, width, 0.2]
rect2 = [left, 0.1, width, 0.5]

fig = plt.figure(facecolor='white')
axescolor  = '#f6f6f6'  # the axes background color
ax1 = fig.add_axes(rect1, axisbg=axescolor)  #left, bottom, width, height
ax2 = fig.add_axes(rect2, axisbg=axescolor, sharex=ax1)
y_target[:training] = 0
ax1.plot((movingAverage(y_predictions, smoothing_win) - movingAverage(y_target, smoothing_win)),"r-", lw=2)
ax1.set_yticks([-500, 0, 500])
ax1.set_yticklabels([-.5, 0, .5])
ax1.set_ylim(-1000, 1000)
ax1.set_ylabel("Error (KW)")
ax2.plot(movingAverage(y_predictions, smoothing_win),color=GRAY, lw=2, label = 'Prediction')
ax2.plot(movingAverage(y_target, smoothing_win), "r--", label = 'Target')
ax2.set_yticks([2000, 4000, 6000])
ax2.set_yticklabels([2, 4, 6])
ax2.set_ylabel("Power (KW)")
ax2.set_xlim(0,len(y_target))
ax2.legend(loc='upper left')

# turn off upper axis tick labels, rotate the lower ones, etc
for ax in ax1, ax2:
    for label in ax.get_xticklabels():
        label.set_visible(False)

plt.savefig('./figures/blr_detection_umass2.pdf')

plt.rc('axes', grid=False)
plt.rc('grid', color='0.75', linestyle='-', linewidth=0.5)
#plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M:%S'))
#plt.gca().xaxis.set_major_locator(mdates.DayLocator())
textsize = 9
left, width = 0.1, 0.8
rect1 = [left, 0.2, width, 0.9]
fig = plt.figure(facecolor='white')
axescolor  = '#f6f6f6'  # the axes background color
ax1 = fig.add_axes(rect1, axisbg=axescolor)  #left, bottom, width, height
p_array = np.asarray(p_array)
hist, bin_edges = np.histogram(p_array, density=True)
numBins = 200
#p_array = p_array[~np.isnan(p_array)]
#ax1.hist(p_array, numBins,color=GRAY, alpha=0.7)
ax1.set_ylabel("P-value distribution")
plt.savefig('./figures/pvalue_distribution_under_H0.pdf')

cursor.close()
cnx.close()
