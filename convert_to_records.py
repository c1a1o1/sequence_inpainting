from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import os
import sys
import dlib
import glob
import h5py
from skimage import io
import time
import numpy as np
import collections
from imutils import face_utils
import cv2
from scipy.misc import imsave

import tensorflow as tf

from tensorflow.contrib.learn.python.learn.datasets import mnist

FLAGS = None

# define a dictionary that maps the indexes of the facial
# landmarks to specific face regions
FACIAL_LANDMARKS_IDXS = collections.OrderedDict([
    ("mouth", (48, 68)),
    ("right_eyebrow", (17, 22)),
    ("left_eyebrow", (22, 27)),
    ("right_eye", (36, 42)),
    ("left_eye", (42, 48)),
    ("nose", (27, 35)),
    ("jaw", (0, 17))
])

def _int64_feature(value):
    return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))

def _bytes_feature(value):
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

def convert_to(images, landmarks, name):
    """Converts a dataset to tfrecords."""
    if images.shape[0] != landmarks.shape[0]:
    	raise ValueError('Images size %d does not match landmarks shape %d.' %
                     (images.shape[0], num_examples))

    rows = images.shape[1]
    cols = images.shape[2]
    depth = images.shape[3]

    landmark_rows = landmarks.shape[1]
    landmark_cols = landmarks.shape[2]
    landmark_depth = landmarks.shape[3]

    filename = os.path.join('data_records2', name + '.tfrecords')
    print('Writing', filename)
    writer = tf.python_io.TFRecordWriter(filename)

    for index in range(images.shape[0]):
        image_raw = images[index].tostring()
        landmark_raw = landmarks[index].tostring()

        example = tf.train.Example(features=tf.train.Features(feature={
            'height': _int64_feature(rows),
            'width': _int64_feature(cols),
            'depth': _int64_feature(depth),
            'landmark_height': _int64_feature(landmark_rows),
            'landmark_width': _int64_feature(landmark_cols),
            'landmark_depth': _int64_feature(landmark_depth),
            'landmark_raw': _bytes_feature(landmark_raw),
            'image_raw': _bytes_feature(image_raw)}))
        
        writer.write(example.SerializeToString())

    writer.close()

def make_key_point_matrix(x,y, W, H, n_grid=16):
    resolution = 1.0/n_grid
    #print "x and y:  ", x,y
    #print "Res: ", resolution
    X = x/float(W)   #normalized coordinate
    Y = y/float(H)
    loc = np.zeros((n_grid, n_grid,1), dtype=bool)
    #print "Loc size is::", loc.nbytes
    X_bin = np.clip(int(X/resolution), 0 ,15)
    Y_bin = np.clip(int(Y/resolution), 0 ,15)
    #print "Selected bins: ", X_bin, Y_bin
    loc[X_bin, Y_bin,0] = 1
    #time.sleep(300)
    return loc

def visualize_facial_landmarks(image, shape, colors=None, alpha=0.75):
    # create two copies of the input image -- one for the
    # overlay and one for the final output image
    overlay = np.ones(image.shape) * 10
    output = image.copy()
 
    # if the colors list is None, initialize it with a unique
    # color for each facial landmark region
    if colors is None:
        colors = [(245, 10, 10), (10, 245, 245), (70, 245, 245),
            (10, 10, 245), (10, 10, 245),
            (245, 245, 10), (199, 71, 133)]


    hull = cv2.convexHull(shape)
    cv2.drawContours(overlay, [hull], -1, (245, 245, 245), -1)

    # loop over the facial landmark regions individually
    for (i, name) in enumerate(FACIAL_LANDMARKS_IDXS.keys()):
        # grab the (x, y)-coordinates associated with the
        # face landmark
        (j, k) = FACIAL_LANDMARKS_IDXS[name]
        pts = shape[j:k]
 
        # check if are supposed to draw the jawline
        if name == "jaw":
            # since the jawline is a non-enclosed facial region,
            # just draw lines between the (x, y)-coordinates
            for l in range(1, len(pts)):
                ptA = tuple(pts[l - 1])
                ptB = tuple(pts[l])
                cv2.line(overlay, ptA, ptB, colors[i], 2)
 
        # otherwise, compute the convex hull of the facial
        # landmark coordinates points and display it
        else:
            hull = cv2.convexHull(pts)
            cv2.drawContours(overlay, [hull], -1, colors[i] , -1)

    overlay[0][0][0] = 0
    overlay[0][0][1] = 0
    overlay[0][0][2] = 0

    overlay[127][127][0] = 255
    overlay[127][127][1] = 255
    overlay[127][127][2] = 255    

    return overlay

if __name__ =='__main__':
    if len(sys.argv) != 2:
        print(
            
            " python prepare_bb_land.py  shape_predictor_68_face_landmarks.dat "
            "You can download a trained facial shape predictor from:\n"
            "    http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2")
        exit()

    predictor_path = sys.argv[1]

    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(predictor_path)

    face_image_list = os.listdir('data/')  # dir of extracted faces
    counter = 0

    image_list, landmark_list = [], []
    tfrecord_ind = 0

    for imgs in face_image_list:
        counter += 1

        filename = os.path.join('data/', imgs) 
          
        img = io.imread(filename)
        arr = np.array(img) 
        H, W, C = arr.shape   # we assume that we are getting face cropped images

        # Ask the detector to find the bounding boxes of each face. The 1 in the
        # second argument indicates that we should upsample the image 1 time. This
        # will make everything bigger and allow us to detect more faces.
        dets = detector(img, 1)
        #print("Number of faces detected: {}".format(len(dets)))
        for k, d in enumerate(dets):
            # Get the landmarks/parts for the face in box d.
            shape = predictor(img, d)
            shape = face_utils.shape_to_np(shape)
     
            key_point_matrix = visualize_facial_landmarks(img, shape)
            key_point_matrix = np.array(key_point_matrix, dtype=np.uint8)

            # imsave('im' + str(len(image_list)) + '.png', arr)
            # imsave('ky' + str(len(image_list)) + '.png', key_point_matrix)
            # raw_input('done')
            image_list.append(arr)
            landmark_list.append(key_point_matrix)

            if len(image_list) == 10000:
                # print (np.max(landmark_list), np.min(landmark_list))#, np.sum(landmark_list[landmark_list == 0]))
                convert_to(np.asarray(image_list), np.asarray(landmark_list), 'celebA_' + str(tfrecord_ind))
                image_list, landmark_list = [], []
                tfrecord_ind += 1
                # raw_input('vbjsid')
        
    convert_to(np.asarray(image_list), np.asarray(landmark_list), 'celebA_' + str(tfrecord_ind))