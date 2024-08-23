# Demo of how to use STIR from python to display some images with matplotlib

# Copyright 2012-06-05 - 2013 Kris Thielemans

# This file is part of STIR.
#
# SPDX-License-Identifier: Apache-2.0
#
# See STIR/LICENSE.txt for details

#%% Initial imports
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
import stir
import stirextra

def display_slices(npimage):
    """
    Display slices of a 3D numpy array with sliders for each dimension and for vmin and vmax.

    Parameters:
    npimage (numpy.ndarray): 3D numpy array to display.
    """
    
    image_max = npimage.max()
    image_min = npimage.min()
    # Create a figure and axes
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))
    plt.subplots_adjust(left=0.25, bottom=0.35)

    # Initial slices
    slice_index1 = npimage.shape[0] // 2
    slice_index2 = npimage.shape[1] // 2
    slice_index3 = npimage.shape[2] // 2

    # Display initial slices
    img1 = ax1.imshow(npimage[slice_index1, :, :], vmin=image_min, vmax=image_max)
    ax1.set_title(f'Slice {slice_index1} (axis 0)')
    img2 = ax2.imshow(npimage[:, slice_index2, :] , vmin=image_min, vmax=image_max)
    ax2.set_title(f'Slice {slice_index2} (axis 1)')
    img3 = ax3.imshow(npimage[:, :, slice_index3], vmin=image_min, vmax=image_max)
    ax3.set_title(f'Slice {slice_index3} (axis 2)')

    # Create slider axes and sliders for dimensions
    ax_slider1 = plt.axes([0.25, 0.25, 0.65, 0.03], facecolor='lightgoldenrodyellow')
    slider1 = Slider(ax_slider1, 'Axis 0', 0, npimage.shape[0] - 1, valinit=slice_index1, valstep=1)

    ax_slider2 = plt.axes([0.25, 0.2, 0.65, 0.03], facecolor='lightgoldenrodyellow')
    slider2 = Slider(ax_slider2, 'Axis 1', 0, npimage.shape[1] - 1, valinit=slice_index2, valstep=1)

    ax_slider3 = plt.axes([0.25, 0.15, 0.65, 0.03], facecolor='lightgoldenrodyellow')
    slider3 = Slider(ax_slider3, 'Axis 2', 0, npimage.shape[2] - 1, valinit=slice_index3, valstep=1)

    # Create slider axes and sliders for vmin and vmax
    ax_slider_vmin = plt.axes([0.25, 0.1, 0.65, 0.03], facecolor='lightgoldenrodyellow')
    slider_vmin = Slider(ax_slider_vmin, 'vmin', image_min, image_max, valinit=image_min)

    ax_slider_vmax = plt.axes([0.25, 0.05, 0.65, 0.03], facecolor='lightgoldenrodyellow')
    slider_vmax = Slider(ax_slider_vmax, 'vmax', image_min, image_max, valinit=image_max)

    # Update functions
    def update1(val):
        slice_index1 = int(slider1.val)
        img1.set_data(npimage[slice_index1, :, :])
        ax1.set_title(f'Slice {slice_index1} (axis 0)')
        fig.canvas.draw_idle()

    def update2(val):
        slice_index2 = int(slider2.val)
        img2.set_data(npimage[:, slice_index2, :])
        ax2.set_title(f'Slice {slice_index2} (axis 1)')
        fig.canvas.draw_idle()

    def update3(val):
        slice_index3 = int(slider3.val)
        img3.set_data(npimage[:, :, slice_index3])
        ax3.set_title(f'Slice {slice_index3} (axis 2)')
        fig.canvas.draw_idle()

    def update_vmin(val):
        vmin = slider_vmin.val
        img1.set_clim(vmin=vmin, vmax=slider_vmax.val)
        img2.set_clim(vmin=vmin, vmax=slider_vmax.val)
        img3.set_clim(vmin=vmin, vmax=slider_vmax.val)
        fig.canvas.draw_idle()

    def update_vmax(val):
        vmax = slider_vmax.val
        img1.set_clim(vmin=slider_vmin.val, vmax=vmax)
        img2.set_clim(vmin=slider_vmin.val, vmax=vmax)
        img3.set_clim(vmin=slider_vmin.val, vmax=vmax)
        fig.canvas.draw_idle()

    # Connect the sliders to the update functions
    slider1.on_changed(update1)
    slider2.on_changed(update2)
    slider3.on_changed(update3)
    slider_vmin.on_changed(update_vmin)
    slider_vmax.on_changed(update_vmax)

    plt.show()


#%% image display

# read an image using STIR
image = stir.FloatVoxelsOnCartesianGrid.read_from_file(
    '../../recon_test_pack/test_image_3.hv')

# convert data to numpy 3d array
npimage = stirextra.to_numpy(image)

print(f"Image shape: {npimage.shape}")
print(f"Image max: {npimage.max()}")
print(f"Image min: {npimage.min()}")

# display slices
display_slices(npimage)