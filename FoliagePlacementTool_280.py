bl_info = {
    "name": "Foliage Placement",
    "author": "Matt Wallace",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Tool Shelf > Foliage Placement Tool",
    "description": "A tool to speed up foliage mesh clump creation in conjunction with UE4-PivotPainter2 workflow.",
    "warning": "",
    "wiki_url": "",
    "category": "Unreal Tools",
    }

import bpy
import random
import math
import mathutils
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import IntProperty, FloatProperty, BoolProperty, PointerProperty
from mathutils import Matrix, Vector, Euler

def NewBaseMesh():
    verts = [Vector((0,2,0)),
             Vector((0,-2,0)),
             Vector((25,-1,0)),
             Vector((25,1,0)),
             Vector((50,0,0))]
    edges = []
    faces = [[0,1,2,3],[4,3,2]]

    newMesh = bpy.data.meshes.new("PivotPainter2_BaseMesh")
    newMesh.from_pydata(verts, edges, faces)
    newMeshObj = bpy.data.objects.new("PivotPainter2_BaseMesh", newMesh)

    return newMeshObj

def GetRandomTransform(maxRot, maxDistance, maxScaleOffset, index) :
    randomX = maxDistance * (random.randint(0,100)/100) * math.pow(-1, (1 - math.ceil((((index % 4) + 1) / 4.0) - .5))) 
    randomY = maxDistance * (random.randint(0,100)/100) * math.pow(-1, (2 - (index % 2)))
    randomPos = (randomX,randomY,0)
    randomYRot = maxRot * random.randint(0, 100) / 100
    scaleMin = min(100, (100 + maxScaleOffset))
    scaleMax = max(100, (100 + maxScaleOffset))
    randomScale = random.randint( scaleMin, scaleMax) / 100
    
    zVector = (0,0,1)
    xVector = Vector(randomPos)
    xVector.normalize()
    zVector = Vector(zVector)
    yVector = zVector.cross(xVector)
    yVector.normalize()

    orientationMatrix = Matrix([xVector, yVector, zVector]).transposed()     
    randomRotMatrix = Euler((0, math.radians (randomYRot), 0), 'XYZ').to_matrix()   
    rotationMatrix = orientationMatrix @ randomRotMatrix
    transformMatrix = Matrix.Translation(randomPos) @ Matrix.Scale(randomScale,4) @ rotationMatrix.to_4x4()
    
    return transformMatrix

# Copies a list of mesh objects and aligns them to the set of placeholder object
def SpawnFoliageCopies(foliageObjects, foliageEmpties):
    foliageCopies = []

    for o in range(len(foliageObjects)):
        foliageCopies.append([])

    for i in range(len(foliageEmpties)):
        placeHolderRotMatrix = foliageEmpties[i].rotation_euler.to_matrix()
        placeHolderPosition = foliageEmpties[i].location
        placeHolderScale = foliageEmpties[i].scale[0]

        for o in range(len(foliageObjects)): 
            currentObj = foliageObjects[o]
            objectCopy = currentObj.copy()
            objectData = currentObj.data.copy()
            objectName = currentObj.name + "_LOD" #+ str(o) #
            newObject = bpy.data.objects.new(objectName, objectData)
            offsetXTransform = Euler((0, math.radians(-90) , 0), 'XYZ').to_matrix()
            rotationMatrix = placeHolderRotMatrix @ offsetXTransform
            objectTransform = Matrix.Translation(placeHolderPosition) @ Matrix.Scale(placeHolderScale,4) @ rotationMatrix.to_4x4()
            newObject.matrix_world = objectTransform
            currentFoliageColl = bpy.data.collections.get(currentObj.name)
            currentFoliageColl.objects.link(newObject)
            foliageCopies[o].append(newObject)

    return foliageCopies

# Creates a set of empty placeholder objects with random location and rotation and values
def SpawnFoliagePlaceholders(foliageCount, maxRot, maxDistance, maxScaleOffset, foliageEmptyColl) :
    foliageEmpties = []

    for i in range(foliageCount):
        copy = bpy.data.objects.new( "FoliagePlaceholder", None )
        copy.empty_display_size = 25
        copy.empty_display_type = 'SINGLE_ARROW'
        copy.matrix_world = GetRandomTransform(maxRot, maxDistance, maxScaleOffset, i)
        foliageEmptyColl.objects.link(copy)
        foliageEmpties.append(copy)

    return foliageEmpties

# Sets a new random transform to a given set of objects
def RespawnSelectedPlaceholders(foliageEmpties, maxRot, maxDistance, maxScaleOffset, foliageEmptyColl) :
    allFoliageEmpties = foliageEmptyColl.objects

    for p in foliageEmpties:
        for i in range(len(allFoliageEmpties)) :
            if p.name == allFoliageEmpties[i].name :
                p.matrix_world = GetRandomTransform(maxRot, maxDistance, maxScaleOffset, i)

    return allFoliageEmpties

# called by operator on UI panel
def main(context, toolFunction):
    scene = context.scene
    data = bpy.data
    layer = bpy.context.view_layer

    foliageCount = scene.foliage_placement_properties.foliage_count
    maxRotation = scene.foliage_placement_properties.max_rotation
    maxDistance = scene.foliage_placement_properties.max_distance
    maxScaleOffset = scene.foliage_placement_properties.max_scale
    
    selectedPlaceholders = []
    selectedFoliage = []
    activeObject = context.active_object
    selectedFoliageNames = []
    placeholderColl = data.collections.get("FoliagePlaceholders")
    placeholderObjects = []

    if placeholderColl :
        placeholderObjects = placeholderColl.objects
    
    # Create new base mesh object and unwrap it.
    if toolFunction == 0 :
        newObj = NewBaseMesh()
        scene.collection.objects.link(newObj)
        bpy.ops.object.select_all(action='DESELECT')
        newObj.select_set(True)
        layer.objects.active = newObj
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action='SELECT') 
        bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)
        bpy.ops.object.editmode_toggle()
    else :
        # Get any selected placeholder empties or foliage copies
        for o in context.selected_objects :
            if o.name.startswith("FoliagePlaceholder") :
                selectedPlaceholders.append(o)
            elif "_LOD" in o.name :
                selectedFoliageNames.append(o.name)
                namespliced = o.name.split("_LOD")
                namestem = namespliced[0]
                foliageObject = scene.objects[namestem]
                if not (foliageObject in selectedFoliage) :
                    selectedFoliage.append(foliageObject)
        # Spawn Empties / Foliage Placement                 
        if toolFunction < 3 :
            if toolFunction == 1 :
                if (len(selectedPlaceholders) > 0) :
                    RespawnSelectedPlaceholders(selectedPlaceholders, maxRotation, maxDistance, maxScaleOffset, placeholderColl)
                else :
                    if "FoliagePlaceholders" in data.collections :
                        for oldCopy in (placeholderObjects) :
                            bpy.data.objects.remove(oldCopy, do_unlink=True)
                    else:
                        placeholderColl = data.collections.new("FoliagePlaceholders")
                        scene.collection.children.link(placeholderColl)
                    placeholderObjects = SpawnFoliagePlaceholders(foliageCount, maxRotation, maxDistance, maxScaleOffset, placeholderColl)
   
            if (len(selectedFoliage) == 0) :
                foliageMeshObjects = []
                for m in context.selected_objects :
                    if m.type == "MESH" :
                        foliageMeshObjects.append(m)
                selectedFoliage = foliageMeshObjects

            if (len(selectedFoliage) > 0) :
                for i in range(len(selectedFoliage)):
                    current_LOD = selectedFoliage[i]
                    if current_LOD.name in data.collections :
                        currentFoliageColl = data.collections.get(current_LOD.name)
                        for oldCopy in currentFoliageColl.objects :
                            bpy.data.objects.remove(oldCopy, do_unlink=True)
                    else :
                        currentFoliageColl = data.collections.new(current_LOD.name)
                        scene.collection.children.link(currentFoliageColl)

                SpawnFoliageCopies( selectedFoliage, placeholderObjects )
                for n in selectedFoliageNames :
                    foliageObject = scene.objects[n]
                    foliageObject.select_set(True)
        #ShowHide Button            
        else :
            isHidden = placeholderColl.hide_viewport
            placeholderColl.hide_viewport = not isHidden
        
    layer.update()  

class FP_OT_ApplyUnrealUnitsOperator(Operator):
    bl_label = "Unreal Units"
    bl_idname = "foliage_placement.apply_unreal_units"
    bl_description = "Set Metric system unit scale to .01 in meters, and increase the view clipping to 100m"
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'
    def execute(self, context):
        bpy.context.scene.unit_settings.system = 'METRIC'
        bpy.context.scene.unit_settings.scale_length = 0.01
        bpy.context.scene.unit_settings.length_unit = 'METERS'
        bpy.context.space_data.clip_end = 10000
            
        return {'FINISHED'}

class FP_OT_AddBaseMeshOperator(Operator):
    bl_label = "Base Mesh"
    bl_idname = "foliage_placement.add_base_mesh"
    bl_description = "Create and select a new grass base mesh oriented along the X axis"
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'
    def execute(self, context):
        units = context.scene.unit_settings
        
        if units.system != 'METRIC' or round(units.scale_length, 2) != 0.01:
            
            self.report({'ERROR'}, "Scene units must be Metric with a Unit Scale of 0.01!")
        
            return {'CANCELLED'}
                        
        else:
            main(context, 0)
            
            return {'FINISHED'}

# create operator class for foliage spawn button
class FP_OT_SpawnFoliageOperator(Operator):
    bl_label = "Spawn"
    bl_idname = "foliage_placement.spawn_foliage"
    bl_description = "Align foliage copies to a *new* set of Empty foliage placeholders"
    
    @classmethod
    def poll(cls, context):
        return True in [(object.type == 'MESH' or (object.name.startswith("FoliagePlaceholder"))) for object in context.selected_objects] and context.mode == 'OBJECT'     #.name.startswith("foo") 
    def execute(self, context):
        units = context.scene.unit_settings
        
        if units.system != 'METRIC' or round(units.scale_length, 2) != 0.01:
            
            self.report({'ERROR'}, "Scene units must be Metric with a Unit Scale of 0.01!")
        
            return {'CANCELLED'}
                        
        else:
            main(context, 1)
            
            return {'FINISHED'}

# create operator class for foliage placement button
class FP_OT_ReplaceFoliageOperator(Operator):
    bl_label = "Replace"
    bl_idname = "foliage_placement.replace_foliage"
    bl_description = "Align foliage copies to the *current* set of Empty foliage placeholders"

    @classmethod
    def poll(cls, context):
        return True in [object.type == 'MESH' for object in context.selected_objects] and context.mode == 'OBJECT' and ("FoliagePlaceholders" in bpy.data.collections)      
    def execute(self, context):
        units = context.scene.unit_settings
        
        if units.system != 'METRIC' or round(units.scale_length, 2) != 0.01:
            
            self.report({'ERROR'}, "Scene units must be Metric with a Unit Scale of 0.01!")
        
            return {'CANCELLED'}
                        
        else:
            main(context, 2)
            
            return {'FINISHED'}

# create operator class for placeholder select button
class FP_OT_ShowHidePlaceholdersOperator(Operator):
    bl_label = "Show/Hide"
    bl_idname = "foliage_placement.showhide_placeholders"
    bl_description = "Show/hide Empty foliage placeholders."
    
    @classmethod
    def poll(cls, context):
        return ("FoliagePlaceholders" in bpy.data.collections)   

    def execute(self, context):
        units = context.scene.unit_settings
        
        if units.system != 'METRIC' or round(units.scale_length, 2) != 0.01:
            
            self.report({'ERROR'}, "Scene units must be Metric with a Unit Scale of 0.01!")
        
            return {'CANCELLED'}
                        
        else:
            main(context, 3)
            
            return {'FINISHED'}

# create property group for user options
class FP_PT_Properties(PropertyGroup):

    foliage_count : IntProperty(
        name = "Foliage Count", 
        description="Number of foliage object copies. (Tip: use values that are multiples of 4",
        default = 12
    )
    max_distance : IntProperty(
        name = "Position",
        description = "Random position offset from origin",
        default = 20
    ) 
    max_rotation : IntProperty(
        name = "Rotation",
        description = "Random pitch rotation",
        default = 10
    ) 
    max_scale : IntProperty(
        name = "Scale Offset",
        description = "Random scale offset",
        default = 50
    )

#create panel class for UI in object mode tool shelf
class FP_PT_FoliagePlacementPanel(Panel):
    bl_label = "Foliage Placement"
    bl_idname = "FP_PT_foliage_placement_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Pivot Painter"
    bl_context = "objectmode"
    
    def draw(self, context):
        scene = context.scene
        layout = self.layout
        
        col = layout.column(align = True)
        col.operator("foliage_placement.apply_unreal_units")
        col.operator("foliage_placement.add_base_mesh")

        split = layout.split()
        col = split.column()
        col.scale_y = 1

        col.prop(scene.foliage_placement_properties, property="foliage_count")
        col.prop(scene.foliage_placement_properties, property="max_distance")
        col.prop(scene.foliage_placement_properties, property="max_rotation")
        col.prop(scene.foliage_placement_properties, property="max_scale")
        
        split = layout.split()
        col = split.column()
        col.scale_y = 1.5
        col.operator("foliage_placement.spawn_foliage")
        col.operator("foliage_placement.replace_foliage")
        col.operator("foliage_placement.showhide_placeholders")

#create register functions for adding and removing script 
classes = ( FP_PT_Properties,
            FP_OT_ApplyUnrealUnitsOperator,
            FP_OT_AddBaseMeshOperator,
            FP_OT_SpawnFoliageOperator, 
            FP_OT_ReplaceFoliageOperator,
            FP_OT_ShowHidePlaceholdersOperator, 
            FP_PT_FoliagePlacementPanel, )

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    bpy.types.Scene.foliage_placement_properties = PointerProperty(type = FP_PT_Properties)

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)

    del bpy.types.Scene.foliage_placement_properties
    
if __name__ == "__main__":
    register()