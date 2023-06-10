from typing import Union
import bmesh, bpy, mathutils, re, math, traceback
from bpy.utils import register_class, unregister_class
from ..utility import *
from ..f3d_material_converter import convertAllBSDFtoF3D
from bpy.types import Scene, Image
import ast
import struct

def gamma_correct_value(val):
    return 1.055 * pow(val, (1/2.4)) - 0.055

def combine_lightmaps(lm_image, ao_image, ao_strength):
    width = lm_image.size[0]
    height = lm_image.size[1]
    combined_name = "lightmap"

    # remove previous gamma corrected image
    for i in bpy.data.images:
        if i.name == combined_name:
            i.user_clear()
            bpy.data.images.remove(i)

    # create gamma corrected image
    combined = bpy.data.images.new(combined_name, width, height)
    combined_pixels = list(lm_image.pixels)
    if ao_image is not None:
        ao_pixels = ao_image.pixels[:] # create a copy (tuple) for read-only access
    for x in range(width):
        for y in range(height):
            offs = (x + int(y * width)) * 4
            for i in range(3):
                if ao_image is not None:
                    val = (ao_pixels[offs + i] * combined_pixels[offs + i]) * ao_strength
                    val += combined_pixels[offs + i] * (1 - ao_strength)
                else:
                    val = combined_pixels[offs + i]
                combined_pixels[offs + i] = gamma_correct_value(val)

    combined.pixels[:] = combined_pixels
    combined.update()
    combined.pack()

    return combined

def create_uv(obj, uv_name):
    # Create the UV
    uv_map = obj.data.uv_layers.new(name=uv_name)

    # Switch to edit mode
    bpy.ops.object.mode_set(mode='EDIT')

    # Deselect all faces and select all faces
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_all(action='SELECT')

    # Select the new UV map
    obj.data.uv_layers.active_index = obj.data.uv_layers.find(uv_name)

    # Run Smart UV Project
    bpy.ops.uv.smart_project()

    # Select the first UV map
    obj.data.uv_layers.active_index = 0

    # Switch back to object mode
    bpy.ops.object.mode_set(mode='OBJECT')

    return uv_map

def create_col(obj, col_name):
    # Create the col
    col = obj.data.vertex_colors.new(name=col_name)

    return col

def convert_uv_to_col(obj, uv_map, col):
    # Get the active mesh
    mesh = obj.data

    # Set the color for each vertex based on its UV coordinates
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            uv_coords = uv_map.data[loop_index].uv  # Get the UV coordinates
            u = int(uv_coords[0] * 65535.0)
            v = int(uv_coords[1] * 65535.0)
            r = (u & 0xFF) / 255.0
            g = ((u >> 8) & 0xFF) / 255.0
            b = (v & 0xFF) / 255.0
            a = ((v >> 8) & 0xFF) / 255.0
            color = (r, g, b, a)  # Set the color based on the UV coordinates
            col.data[loop_index].color = color
            #print('color: ' + str(uv_coords[1]) + " :: " + str(color[3]) + " :: " + str(int(b * 255)) + ", " + str(int(a * 255)))

    # Update the mesh to reflect the changes
    mesh.update()

def convert_for_lightmap():
    lightmap = combine_lightmaps(bpy.context.scene.get("CoopLMImage"), bpy.context.scene.get("CoopAOImage"), bpy.context.scene.CoopAOStrength)

    # check object mode
    if bpy.context.mode != "OBJECT":
        raise PluginError("Operator can only be used in object mode.")

    # check for selection
    if len(bpy.context.selected_objects) == 0:
        raise PluginError("Mesh not selected.")
    elif type(bpy.context.selected_objects[0].data) is not bpy.types.Mesh:
        raise PluginError("Mesh not selected.")

    # hide the selected object
    original_obj = bpy.context.active_object

    # Duplicate the selected object
    obj = original_obj.copy()
    obj.data = original_obj.data.copy()
    obj.animation_data_clear()
    bpy.context.collection.objects.link(obj)
    obj.name = obj.name + '_mapped'
    obj.select_set(True)
    original_obj.hide_set(True)

    # create the uv map if it doesn't exist
    uv_map = None
    uv_map_name = None
    if len(obj.data.uv_layers) < 1:
        raise PluginError("No regular UV map.")
    elif len(obj.data.uv_layers) < 2:
        uv_map = create_uv(obj, 'Lightmap')
    else:
        uv_map = obj.data.uv_layers[1]

    # error check
    if uv_map is None:
        raise PluginError("Could not generate or find second uv map.")
    uv_map_name = uv_map.name

    # create the col if it doesn't exist
    col = None
    col_name = 'UVColors'
    if col_name not in obj.data.vertex_colors:
        col = create_col(obj, col_name)
    else:
        col = obj.data.vertex_colors[col_name]

    # error check
    if col is None:
        raise PluginError("Could not generate or find vertex colors.")

    # convert the UV map to vertex colors
    convert_uv_to_col(obj, obj.data.uv_layers[uv_map_name], col)

    # build up lightmap info
    lightmap_info = {
        'uv': uv_map_name,
        'tex': lightmap
    }
    # convert the materials to F3D
    convertAllBSDFtoF3D([obj], False, lightmap_info = lightmap_info)
    # inject the uv map into the F3D material


class F3D_Coop(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.f3d_convert_uvs"
    bl_label = "Apply Lightmap"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        try:
            convert_for_lightmap()

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set

class F3D_CoopPanel(bpy.types.Panel):
    bl_idname = "F3D_PT_Coop"
    bl_label = "Coop"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Coop"

    @classmethod
    def poll(cls, context):
        return True

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        prop_split(col, context.scene, "CoopLMImage", "Lightmap Image")
        prop_split(col, context.scene, "CoopAOImage", "Ambient Occlusion Image")
        prop_split(col, context.scene, "CoopAOStrength", "Ambient Occlusion Strength")
        col.operator(F3D_Coop.bl_idname)

f3d_coop_classes = (
    F3D_Coop,
    F3D_CoopPanel
)

def f3d_coop_register():
    for cls in f3d_coop_classes:
        register_class(cls)

    bpy.types.Scene.CoopLMImage    = bpy.props.PointerProperty(name="CoopLMImage", type=Image)
    bpy.types.Scene.CoopAOImage    = bpy.props.PointerProperty(name="CoopAOImage", type=Image)
    bpy.types.Scene.CoopAOStrength = bpy.props.FloatProperty(name="CoopAOStrength", default=0.75)


def f3d_coop_unregister():
    for cls in reversed(f3d_coop_classes):
        unregister_class(cls)

    del bpy.types.Scene.CoopLMImage
    del bpy.types.Scene.CoopAOImage
    del bpy.types.Scene.CoopAOStrength
