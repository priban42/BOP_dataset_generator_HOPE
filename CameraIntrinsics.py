"""Camera utility, collection of useful camera functions."""
from typing import Union

import bpy
from mathutils import Matrix
import numpy as np


def __set_intrinsics_from_blender_params(lens: float = None, image_width: int = None, image_height: int = None,
                                         pixel_aspect_x: float = None, pixel_aspect_y: float = None,
                                         shift_x: int = None,
                                         shift_y: int = None, lens_unit: str = None):
    """ Sets the camera intrinsics using blenders represenation.

    :param lens: Either the focal length in millimeters or the FOV in radians, depending on the given lens_unit.
    :param image_width: The image width in pixels.
    :param image_height: The image height in pixels.
    :param clip_start: Clipping start.
    :param clip_end: Clipping end.
    :param pixel_aspect_x: The pixel aspect ratio along x.
    :param pixel_aspect_y: The pixel aspect ratio along y.
    :param shift_x: The shift in x direction.
    :param shift_y: The shift in y direction.
    :param lens_unit: Either FOV or MILLIMETERS depending on whether the lens is defined as focal length in
                      millimeters or as FOV in radians.
    """

    cam_ob = bpy.context.scene.camera
    cam = cam_ob.data

    if lens_unit is not None:
        cam.lens_unit = lens_unit

    if lens is not None:
        # Set focal length
        if cam.lens_unit == 'MILLIMETERS':
            if lens < 1:
                raise Exception(
                    "The focal length is smaller than 1mm which is not allowed in blender: " + str(lens))
            cam.lens = lens
        elif cam.lens_unit == "FOV":
            cam.angle = lens
        else:
            raise Exception("No such lens unit: " + lens_unit)

    # Set resolution
    if image_width is not None:
        bpy.context.scene.render.resolution_x = image_width
    if image_height is not None:
        bpy.context.scene.render.resolution_y = image_height

    # Set aspect ratio
    if pixel_aspect_x is not None:
        bpy.context.scene.render.pixel_aspect_x = pixel_aspect_x
    if pixel_aspect_y is not None:
        bpy.context.scene.render.pixel_aspect_y = pixel_aspect_y

    # Set shift
    if shift_x is not None:
        cam.shift_x = shift_x
    if shift_y is not None:
        cam.shift_y = shift_y


def __get_view_fac_in_px(cam: bpy.types.Camera, pixel_aspect_x: float, pixel_aspect_y: float,
                         resolution_x_in_px: int, resolution_y_in_px: int) -> int:
    """ Returns the camera view in pixels.

    :param cam: The camera object.
    :param pixel_aspect_x: The pixel aspect ratio along x.
    :param pixel_aspect_y: The pixel aspect ratio along y.
    :param resolution_x_in_px: The image width in pixels.
    :param resolution_y_in_px: The image height in pixels.
    :return: The camera view in pixels.
    """
    # Determine the sensor fit mode to use
    if cam.sensor_fit == 'AUTO':
        if pixel_aspect_x * resolution_x_in_px >= pixel_aspect_y * resolution_y_in_px:
            sensor_fit = 'HORIZONTAL'
        else:
            sensor_fit = 'VERTICAL'
    else:
        sensor_fit = cam.sensor_fit

    # Based on the sensor fit mode, determine the view in pixels
    pixel_aspect_ratio = pixel_aspect_y / pixel_aspect_x
    if sensor_fit == 'HORIZONTAL':
        view_fac_in_px = resolution_x_in_px
    else:
        view_fac_in_px = pixel_aspect_ratio * resolution_y_in_px

    return view_fac_in_px


def set_intrinsics_from_K_matrix(K: Union[np.ndarray, Matrix], image_width: int, image_height: int):
    """ Set the camera intrinsics via a K matrix.

    The K matrix should have the format:
        [[fx, 0, cx],
         [0, fy, cy],
         [0, 0,  1]]

    This method is based on https://blender.stackexchange.com/a/120063.

    :param K: The 3x3 K matrix.
    :param image_width: The image width in pixels.
    :param image_height: The image height in pixels.
    :param clip_start: Clipping start.
    :param clip_end: Clipping end.
    """

    K = Matrix(K)

    cam = bpy.context.scene.camera.data

    if abs(K[0][1]) > 1e-7:
        raise ValueError(f"Skew is not supported by blender and therefore "
                         f"not by BlenderProc, set this to zero: {K[0][1]} and recalibrate")

    fx, fy = K[0][0], K[1][1]
    cx, cy = K[0][2], K[1][2]

    # If fx!=fy change pixel aspect ratio
    pixel_aspect_x = pixel_aspect_y = 1
    if fx > fy:
        pixel_aspect_y = fx / fy
    elif fx < fy:
        pixel_aspect_x = fy / fx

    # Compute sensor size in mm and view in px
    pixel_aspect_ratio = pixel_aspect_y / pixel_aspect_x
    view_fac_in_px = __get_view_fac_in_px(cam, pixel_aspect_x, pixel_aspect_y, image_width, image_height)
    sensor_size_in_mm = get_sensor_size(cam)

    # Convert focal length in px to focal length in mm
    f_in_mm = fx * sensor_size_in_mm / view_fac_in_px

    # Convert principal point in px to blenders internal format
    shift_x = (cx - (image_width - 1) / 2) / -view_fac_in_px
    shift_y = (cy - (image_height - 1) / 2) / view_fac_in_px * pixel_aspect_ratio

    # Finally set all intrinsics
    __set_intrinsics_from_blender_params(f_in_mm, image_width, image_height, pixel_aspect_x, pixel_aspect_y, shift_x, shift_y, "MILLIMETERS")


def get_sensor_size(cam: bpy.types.Camera) -> float:
    """ Returns the sensor size in millimeters based on the configured sensor_fit.

    :param cam: The camera object.
    :return: The sensor size in millimeters.
    """
    if cam.sensor_fit == 'VERTICAL':
        sensor_size_in_mm = cam.sensor_height
    else:
        sensor_size_in_mm = cam.sensor_width
    return sensor_size_in_mm

def get_intrinsics_as_K_matrix() -> np.ndarray:
    """ Returns the current set intrinsics in the form of a K matrix.

    This is basically the inverse of the the set_intrinsics_from_K_matrix() function.

    :return: The 3x3 K matrix
    """
    cam_ob = bpy.context.scene.camera
    cam = cam_ob.data

    f_in_mm = cam.lens
    resolution_x_in_px = bpy.context.scene.render.resolution_x
    resolution_y_in_px = bpy.context.scene.render.resolution_y

    # Compute sensor size in mm and view in px
    pixel_aspect_ratio = bpy.context.scene.render.pixel_aspect_y / bpy.context.scene.render.pixel_aspect_x
    view_fac_in_px = __get_view_fac_in_px(cam, bpy.context.scene.render.pixel_aspect_x,
                                          bpy.context.scene.render.pixel_aspect_y,
                                          resolution_x_in_px, resolution_y_in_px)
    sensor_size_in_mm = get_sensor_size(cam)

    # Convert focal length in mm to focal length in px
    fx = f_in_mm / sensor_size_in_mm * view_fac_in_px
    fy = fx / pixel_aspect_ratio

    # Convert principal point in blenders format to px
    cx = (resolution_x_in_px - 1) / 2 - cam.shift_x * view_fac_in_px
    cy = (resolution_y_in_px - 1) / 2 + cam.shift_y * view_fac_in_px / pixel_aspect_ratio

    # Build K matrix
    K = np.array([[fx, 0, cx],
                  [0, fy, cy],
                  [0, 0, 1]])
    return K


def main():
    import os
    dir = os.path.dirname(bpy.data.filepath)
    my_K = Matrix(
        ((614.193, 0, 326.268),
         (0, 614.193, 238.851),
         (0, 0, 1)))

    set_intrinsics_from_K_matrix(K=my_K, image_width=640, image_height=480)
    print(get_intrinsics_as_K_matrix())


if __name__ == "__main__":
    main()