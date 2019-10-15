bl_info = {
    "name": "Foliage Placement",
    "author": "Matt Wallace",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Tool Shelf > Foliage Placement Tool",
    "description": "A tool to speed up foliage mesh clump creation suited for UE4-PivotPainter2 workflow.",
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

# create new base mesh object.
def NewBaseMesh():
    verts = [Vector((0,2,0)),
             Vector((0,-2,0)),
             Vector((25,-1,0)),
             Vector((25,1,0)),
             Vector((50,0,0))]
    edges = []
    faces = [[0,1,2,3],[4,3,2]]

    newMesh = bpy.data.meshes.new("FoliageMesh")
    newMesh.from_pydata(verts, edges, faces)
    newMeshObj = bpy.data.objects.new("FoliageMesh", newMesh)

    return newMeshObj

# creates a new foliage transform based on user transform parameters and the object list index (used to determine grid location).
def GetRandomTransform(maxRot, maxDistance, maxScaleOffset, index):
    # calculate random grid location from index 
    randomX = maxDistance * (random.randint(0,100)/100) * math.pow(-1, (1 - math.ceil((((index % 4) + 1) / 4.0) - .5))) 
    randomY = maxDistance * (random.randint(0,100)/100) * math.pow(-1, (2 - (index % 2)))
    randomPos = (randomX,randomY,0)

    distance = Vector(randomPos).length
    distanceRatio = distance / Vector((maxDistance, maxDistance, 0)).length
    randomYRot = maxRot * distanceRatio #randomYRot = maxRot * random.randint(0, 100) / 100
    randomRotMatrix = Euler((0, math.radians (randomYRot), 0), 'XYZ').to_matrix()

    scaleMin = min(100, (100 + maxScaleOffset))
    scaleMax = max(100, (100 + maxScaleOffset))
    randomScale = random.randint(scaleMin, scaleMax) / 100
    
    zVector = (0,0,1)
    xVector = Vector(randomPos)
    xVector.normalize()
    zVector = Vector(zVector)
    yVector = zVector.cross(xVector)
    yVector.normalize()
    orientationMatrix = Matrix([xVector, yVector, zVector]).transposed()        
    rotationMatrix = orientationMatrix @ randomRotMatrix

    transformMatrix = Matrix.Translation(randomPos) @ Matrix.Scale(randomScale,4) @ rotationMatrix.to_4x4()
    
    return transformMatrix

# copies a list of mesh objects and aligns them to the set of placeholder object
def SpawnFoliageCopies(foliageObjects, foliageEmpties, foliageNameSuffix):
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
            objectName = currentObj.name + foliageNameSuffix
            newObject = bpy.data.objects.new(objectName, objectData)
            offsetXTransform = Euler((0, math.radians(-90), 0), 'XYZ').to_matrix()
            rotationMatrix = placeHolderRotMatrix @ offsetXTransform
            objectTransform = Matrix.Translation(placeHolderPosition) @ Matrix.Scale(placeHolderScale, 4) @ rotationMatrix.to_4x4()
            newObject.matrix_world = objectTransform
            foliageColl = bpy.data.collections.get(currentObj.name)
            foliageColl.objects.link(newObject)
            foliageCopies[o].append(newObject)

    return foliageCopies

# creates a set of empty placeholder objects with random location and rotation and values
def SpawnFoliagePlaceholders(foliageCount, maxRot, maxDistance, maxScaleOffset, foliageEmptyColl) :
    foliageEmpties = []

    for i in range(foliageCount):
        copy = bpy.data.objects.new("FoliageEmpty", None)
        copy.empty_display_size = 20
        copy.empty_display_type = 'SINGLE_ARROW'
        copy.matrix_world = GetRandomTransform(maxRot, maxDistance, maxScaleOffset, i)
        foliageEmptyColl.objects.link(copy)
        foliageEmpties.append(copy)

    return foliageEmpties

# creates a set of empty placeholders aligned to a set of foliage copies
def SpawnPlaceholdersToObjects(foliageObjects, foliageEmptyColl) :
    foliageEmpties = []
    RotateXMatrix = Euler((0, math.radians(90), 0), 'XYZ').to_matrix()
    
    for o in foliageObjects :
    	objectPosition = o.location
        objectScale = o.scale[0]
        objectRotMatrix = o.rotation_euler.to_matrix()
        rotationMatrix = objectRotMatrix @ RotateXMatrix
        objectTransform = Matrix.Translation(objectPosition) @ Matrix.Scale(objectScale, 4) @ rotationMatrix.to_4x4()

        copy = bpy.data.objects.new("FoliageEmpty", None)
        copy.empty_display_size = 20
        copy.empty_display_type = 'SINGLE_ARROW'
        copy.matrix_world = objectTransform
        foliageEmptyColl.objects.link(copy)
        foliageEmpties.append(copy)

    return foliageEmpties

# sets a new random transform to a given set of objects
def RespawnSelectedPlaceholders(foliageEmpties, maxRot, maxDistance, maxScaleOffset, foliageEmptyColl) :
    allFoliageEmpties = foliageEmptyColl.objects

    for p in foliageEmpties:
        for i in range(len(allFoliageEmpties)) :
            if p.name == allFoliageEmpties[i].name :
                p.matrix_world = GetRandomTransform(maxRot, maxDistance, maxScaleOffset, i)

    return allFoliageEmpties

def GetFoliageCopyReference(foliageCopyName, foliageNameSuffix) :
    namesplit = foliageCopyName.split(foliageNameSuffix)
    objectName = namesplit[0]
    objectRef = bpy.context.scene.objects[objectName]

    return objectRef

# called by Spawn and Placement operators on UI panel
def main(context, toolFunction):
    scene = context.scene
    data = bpy.data
    layer = bpy.context.view_layer

    # get cluster parameters from tool property group
    foliageCount = scene.foliage_placement_properties.foliage_count
    maxRotation = scene.foliage_placement_properties.max_rotation
    maxDistance = scene.foliage_placement_properties.max_distance
    maxScaleOffset = scene.foliage_placement_properties.max_scale

    # get placeholder object collection 
    placeholderObjects = []
    placeholderColl = data.collections.get("FoliagePlaceholders")
    if placeholderColl :
        placeholderObjects = placeholderColl.objects
    
    # object name suffix used to distinguish foliage copies
    foliageNameSuffix = "_FPTool"
    activeObjectName = context.active_object.name
    # separate selected objects into placeholders, foliage copies, and foliage mesh objects
    selectedCopyNames = []
    foliageCopyRefs = []
    foliageMeshObjects = []
    selectedPlaceholders = []
    for o in context.selected_objects :
        if o.name.startswith("FoliageEmpty") :
            selectedPlaceholders.append(o)
        elif foliageNameSuffix in o.name :
            foliageObject = GetFoliageCopyReference(o.name, foliageNameSuffix)
            selectedCopyNames.append(o.name)
            if not (foliageObject in foliageCopyRefs) :
                foliageCopyRefs.append(foliageObject)
        elif o.type == "MESH" :
            foliageMeshObjects.append(o)

    if toolFunction == 1 :
        if (len(selectedPlaceholders) > 0) or (len(foliageCopyRefs) > 0) :
            # get placeholders for selected copies
            if (len(foliageCopyRefs) > 0) :
                selectedPlaceholders = []
                for i in range(len(selectedCopyNames)) :
                    foliageObject = GetFoliageCopyReference(selectedCopyNames[i], foliageNameSuffix)
                    foliageColl = data.collections.get(foliageObject.name)
                    if len(placeholderObjects) != len(foliageColl.objects) or placeholderObjects[0].location != foliageColl.objects[0].location :
                    	for oldCopy in (placeholderObjects) :
                    		bpy.data.objects.remove(oldCopy, do_unlink=True)
                    	placeholderObjects = SpawnPlaceholdersToObjects(foliageColl.objects, placeholderColl)
                    for j in range(len(foliageColl.objects)) :
                        if selectedCopyNames[i] == foliageColl.objects[j].name :
                            selectedPlaceholders.append(placeholderObjects[j])
            # respawn placeholder objects
            RespawnSelectedPlaceholders(selectedPlaceholders, maxRotation, maxDistance, maxScaleOffset, placeholderColl)
        else :
            # clear current foliage placeholder collection, or create a new one
            if "FoliagePlaceholders" in data.collections :
                for oldCopy in (placeholderObjects) :
                    bpy.data.objects.remove(oldCopy, do_unlink=True)
            else:
                placeholderColl = data.collections.new("FoliagePlaceholders")
                scene.collection.children.link(placeholderColl)
            
            placeholderObjects = SpawnFoliagePlaceholders(foliageCount, maxRotation, maxDistance, maxScaleOffset, placeholderColl)

    # pick selected mesh objects if there are no foliage copy references
    if (len(foliageCopyRefs) == 0 and len(foliageMeshObjects) > 0) :        
        foliageCopyRefs = foliageMeshObjects

    # spawn foliage mesh copies
    if (len(foliageCopyRefs) > 0) :
        # clear current foliage copy collections or create new ones
        for i in range(len(foliageCopyRefs)):
            foliageRef = foliageCopyRefs[i]
            foliageColl = data.collections.get(foliageRef.name)
            if foliageColl : #and len(foliageColl.objects) > 0 :
                if toolFunction == 2 and len(foliageColl.objects) > 0 and (len(placeholderObjects) != len(foliageColl.objects) or placeholderObjects[0].location != foliageColl.objects[0].location) :
                	for oldCopy in (placeholderObjects) :
                    	bpy.data.objects.remove(oldCopy, do_unlink=True)
                    placeholderObjects = SpawnPlaceholdersToObjects(foliageColl.objects, placeholderColl)
                for oldCopy in foliageColl.objects :
                    bpy.data.objects.remove(oldCopy, do_unlink=True)
            else :
                foliageColl = data.collections.new(foliageRef.name)
                scene.collection.children.link(foliageColl)

        SpawnFoliageCopies(foliageCopyRefs, placeholderObjects, foliageNameSuffix)

        # reselect foliage copies that were previously cleared
        for n in selectedCopyNames :
            foliageObject = scene.objects.get(n)
            if foliageObject :
                foliageObject.select_set(True)
                if foliageObject.name == activeObjectName :
                	layer.objects.active = foliageObject
    # remove garbage
    for block in bpy.data.meshes:
	    if block.users == 0:
	        bpy.data.meshes.remove(block)

    layer.update()

# create operator class for unit scale button
class FP_OT_ApplyUnrealUnitsOperator(Operator):
    bl_label = "Unreal Units"
    bl_idname = "foliage_placement.apply_unreal_units"
    bl_description = "Set Metric system unit scale to .01 in meters, and increase the view clipping to 100m"
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'
    def execute(self, context):
        # set system unit scale, and extend view clipping distance 
        bpy.context.scene.unit_settings.system = 'METRIC'
        bpy.context.scene.unit_settings.scale_length = 0.01
        bpy.context.scene.unit_settings.length_unit = 'METERS'
        bpy.context.space_data.clip_end = 10000
            
        return {'FINISHED'}

# create operator class for mesh creation button
class FP_OT_AddBaseMeshOperator(Operator):
    bl_label = "Mesh"
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
            # create new base mesh object
            newObj = NewBaseMesh()
            newObj.location = (-25,-50,0)
            context.scene.collection.objects.link(newObj)
            bpy.ops.object.select_all(action='DESELECT')
            newObj.select_set(True)
            context.view_layer.objects.active = newObj
            bpy.ops.object.editmode_toggle()
            bpy.ops.mesh.select_all(action='SELECT') 
            bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)
            bpy.ops.object.editmode_toggle()
            
            return {'FINISHED'}

# create operator class for foliage spawn button
class FP_OT_SpawnFoliageOperator(Operator):
    bl_label = "Spawn"
    bl_idname = "foliage_placement.spawn_foliage"
    bl_description = "Align foliage copies to a *new* set of Empty foliage placeholders"
    
    @classmethod
    def poll(cls, context):
        return True in [object.type == 'MESH' for object in context.selected_objects] and context.mode == 'OBJECT'
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
    bl_label = "Place"
    bl_idname = "foliage_placement.place_foliage"
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
class FP_OT_TogglePlaceholdersOperator(Operator):
    bl_label = "Empties"
    bl_idname = "foliage_placement.toggle_placeholders"
    bl_description = "Show/hide Empty foliage placeholders"
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and ("FoliagePlaceholders" in bpy.data.collections) and len(bpy.data.collections.get("FoliagePlaceholders").objects) > 0   

    def execute(self, context):
        units = context.scene.unit_settings
        
        if units.system != 'METRIC' or round(units.scale_length, 2) != 0.01:
            
            self.report({'ERROR'}, "Scene units must be Metric with a Unit Scale of 0.01!")
        
            return {'CANCELLED'}
                        
        else:
            # toggle empty placeholder object visibility
            placeholderColl = bpy.data.collections.get("FoliagePlaceholders")
            isHidden = placeholderColl.hide_viewport
            placeholderColl.hide_viewport = not isHidden
            
            return {'FINISHED'}

# create operator class for placeholder select button
class FP_OT_SelectFoliageCopiesOperator(Operator):
    bl_label = "Select"
    bl_idname = "foliage_placement.select_copies"
    bl_description = "Select foliage copies associated with the current selection"
    
    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT') and ("FoliagePlaceholders" in bpy.data.collections) and True in [(object.type == 'MESH' or (object.name.startswith("FoliageEmpty"))) for object in context.selected_objects]   

    def execute(self, context):
        units = context.scene.unit_settings
        
        if units.system != 'METRIC' or round(units.scale_length, 2) != 0.01:
            
            self.report({'ERROR'}, "Scene units must be Metric with a Unit Scale of 0.01!")
        
            return {'CANCELLED'}
                        
        else:
            foliageNameSuffix = "_FPTool"
            selectedObjects = context.selected_objects
            bpy.ops.object.select_all(action='DESELECT')
            for c in selectedObjects :
                foliageObjectName = c.name
                foliageColl = bpy.data.collections.get(c.name)
                if foliageNameSuffix in c.name :
                    foliageObjectName = GetFoliageCopyReference(c.name, foliageNameSuffix).name
                    foliageColl = bpy.data.collections.get(foliageObjectName)
                elif c.name.startswith("FoliageEmpty") :
                    foliageColl = bpy.data.collections.get("FoliagePlaceholders")
                if foliageColl : 
                    for o in foliageColl.objects :
                        o.select_set(True)
            if len(context.selected_objects) == 0 :
                for n in selectedObjects :
                    n.select_set(True)

            return {'FINISHED'}

# create property group for user options
class FP_PT_Properties(PropertyGroup):

    foliage_count : IntProperty(
        name = "Foliage Count", 
        description="Number of foliage object copies. (Tip: use values that are multiples of 4",
        default = 8
    )
    max_distance : IntProperty(
        name = "Position",
        description = "Random position offset from origin",
        default = 10
    ) 
    max_rotation : IntProperty(
        name = "Rotation",
        description = "Max pitch rotation angle",
        default = 10
    ) 
    max_scale : IntProperty(
        name = "Scale Offset",
        description = "Random scale offset",
        default = 50
    )

# create panel class for UI in object mode tool shelf
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
        col.operator("foliage_placement.add_base_mesh")
        col.operator("foliage_placement.spawn_foliage")
        col.operator("foliage_placement.place_foliage")
        col.operator("foliage_placement.select_copies")
        col.operator("foliage_placement.toggle_placeholders")

# create register functions for adding and removing script 
classes = ( FP_PT_Properties,
            FP_OT_ApplyUnrealUnitsOperator,
            FP_OT_AddBaseMeshOperator,
            FP_OT_SpawnFoliageOperator, 
            FP_OT_ReplaceFoliageOperator,
            FP_OT_TogglePlaceholdersOperator,
            FP_OT_SelectFoliageCopiesOperator, 
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
