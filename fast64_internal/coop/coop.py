from typing import Union
import bmesh, bpy, mathutils, re, math, traceback
from bpy.utils import register_class, unregister_class
from ..utility import *
import ast
import struct

def create_uv(uv_name):
    # Get the selected object
    obj = bpy.context.active_object

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

def create_col(col_name):
    # Get the selected object
    obj = bpy.context.active_object

    # Create the col
    col = obj.data.vertex_colors.new(name=col_name)

    return col

def convert_uv_to_col(uv_map, col):
    # Get the active object
    obj = bpy.context.active_object

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
            print('color: ' + str(uv_coords[1]) + " :: " + str(color[3]) + " :: " + str(int(b * 255)) + ", " + str(int(a * 255)))

    # Update the mesh to reflect the changes
    mesh.update()

def convert_for_lightmap():
    # Get the selected object
    obj = bpy.context.active_object

    # Switch to object mode
    bpy.ops.object.mode_set(mode='OBJECT')

    # create the uv map if it doesn't exist
    uv_map = None
    uv_name = 'SimpleBake'
    if uv_name not in obj.data.uv_layers:
        uv_map = create_uv(uv_name)
    else:
        uv_map = obj.data.uv_layers[uv_name]

    # create the col if it doesn't exist
    col = None
    col_name = 'UVColors'
    if col_name not in obj.data.vertex_colors:
        col = create_col(col_name)
    else:
        col = obj.data.vertex_colors[col_name]

    convert_uv_to_col(uv_map, col)

class F3D_Coop(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.f3d_convert_uvs"
    bl_label = "Convert UVs"
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

        col.operator(F3D_Coop.bl_idname)
        prop_split(col, context.scene, "CoopUVName", "UV Name")
        prop_split(col, context.scene, "CoopVtxColName", "Vtx Color Name")

f3d_coop_classes = (
    F3D_Coop,
    F3D_CoopPanel
)

def f3d_coop_register():
    for cls in f3d_coop_classes:
        register_class(cls)

    bpy.types.Scene.CoopUVName = bpy.props.StringProperty(name="UVName")
    bpy.types.Scene.CoopVtxColName = bpy.props.StringProperty(name="VtxColName")


def f3d_coop_unregister():
    for cls in reversed(f3d_coop_classes):
        unregister_class(cls)

    del bpy.types.Scene.CoopUVName
    del bpy.types.Scene.CoopVtxColName
