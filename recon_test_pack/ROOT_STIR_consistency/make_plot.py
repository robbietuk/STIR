#%%
import os

import numpy as npy
import matplotlib.pyplot as plt
import itertools
import statistics

os.chdir("/Users/roberttwyman/bin/STIR/TOF/STIR/recon_test_pack/ROOT_STIR_consistency")


class Coord:
    def __init__(self, x, y, z, weight=None):
        self.x = x
        self.y = y
        self.z = z
        self.weight = weight



def read_file_coords(filename):
    with open(filename,'r') as f:
        line_content = f.readlines()
    f.close()

    line_content = [x.split() for x in line_content]
    event_list = []
    for event in line_content:
        if len(event) > 3:
            event_list.append(Coord(float(event[0]), float(event[1]), float(event[2]), float(event[3])))
        else:
            event_list.append(Coord(float(event[0]), float(event[1]), float(event[2])))
    # xlist = [float(x[0]) for x in line_content]
    # ylist = [float(x[1]) for x in line_content]
    # zlist = [float(x[2]) for x in line_content]
    # if len(line_content[0]) > 3:
    #     weightlist = [float(x[3]) for x in line_content ]
    #     return [xlist,ylist,zlist,weightlist]
    # return [xlist, ylist, zlist]
    return event_list

class CoordinateData:
    def __init__(self, image_file_name):
        # Filenames
        self.image_file_name = image_file_name
        self.lor_pos_file_name = image_file_name.split(".")[0] + "_lor_pos.txt"
        self.origin_and_COM_file_name = image_file_name.split(".")[0] + "_ORIG_and_COM.txt"

        self.lor_coordinates_list = None
        self.origin_coordinate = None
        self.COM_coordinate = None

        self.load_data()


    def load_data(self):
        self.lor_coordinates_list = read_file_coords(self.lor_pos_file_name)
        tmp_ORIG_and_COM = read_file_coords(self.origin_and_COM_file_name)
        self.origin_coordinate = tmp_ORIG_and_COM[0]
        self.COM_coordinate = tmp_ORIG_and_COM[1]

    def get_lor_pos_x_list(self):
        return [event.x for event in self.lor_coordinates_list]

    def get_lor_pos_y_list(self):
        return [event.y for event in self.lor_coordinates_list]

    def get_lor_pos_z_list(self):
        return [event.z for event in self.lor_coordinates_list]

    def get_lor_pos_weights_list(self):
        return [event.weight for event in self.lor_coordinates_list]


# Discontinued function
# def extract_coordinates2(filename):
#     with open(filename,'r') as f:
#         line_content = f.readlines()
#     f.close()
#     line_content = [x.split() for x in line_content]
#     listcont = [[x[0],x[1],x[2]] for x in line_content ]
#     return listcont


def make_scatter_plot(coord_data, hide_lor_pos=False):

    plt.figure()
    legend = []

    if not hide_lor_pos:
        # lor positions (all of them)
        plt.scatter(coord_data.get_lor_pos_x_list(),coord_data.get_lor_pos_y_list(), marker="x")
        legend.append("TOF Max LOR Coordinates")

    # Add origin position
    plt.scatter(coord_data.origin_coordinate.x, coord_data.origin_coordinate.y)
    # plot Center of Mass position and add error bars based upon standerd deviation
    # plt.scatter(coord_data.COM_coordinate.x, coord_data.COM_coordinate.y)
    plt.errorbar(coord_data.COM_coordinate.x, coord_data.COM_coordinate.y,
                 xerr=statistics.pstdev(coord_data.get_lor_pos_x_list()),
                 yerr=statistics.pstdev(coord_data.get_lor_pos_y_list()),
                 linestyle='-', color='r')

    legend += ['Origin Coordinate', "COM Coordinate"]
    plt.xlabel("x value (mm)")
    plt.ylabel("y value (mm)")
    plt.title("TOF kernel")
    plt.legend(legend)
    plt.show()
    
def threshold_values(xsource,ysource,zsource,listcont):
    distance=[]
    boollist=[]
    for x in listcont:
        distance.append(npy.sqrt(npy.power(float(x[0])-xsource,2)+npy.power(float(x[1])-ysource,2)+npy.power(float(x[2])-zsource,2)))
    for d in distance:
        boollist.append(d > 45)
    return boollist

def make_plots(coord_data):
    make_scatter_plot(coord_data, hide_lor_pos=True)
    make_scatter_plot(coord_data, hide_lor_pos=False)




#%%
def main():
    # TODO image_file_name should be set by argument
    image_file_name = "stir_image5.hv"
    coord_data = CoordinateData(image_file_name)
    make_plots(coord_data)

if __name__ == "__main__":
    main()
