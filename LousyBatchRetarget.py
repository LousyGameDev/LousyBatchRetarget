import maya.cmds as cmds
import maya.mel as mel
import os
import maya.api.OpenMaya as om


# Global variable to store imported joint UUIDs
imported_joint_uuids = []



# === IMPORT ANIMATION ===
def get_new_root_joint(before_import):
    """
    Identifies the new root joint by comparing joint lists before and after import.
    """
    after_import = cmds.ls(type="joint")  # Get joints after import
    new_joints = list(set(after_import) - set(before_import))  # Find new ones

    if not new_joints:
        cmds.warning("⚠ No new joints detected after import!")
        return None

    for joint in new_joints:
        if not cmds.listRelatives(joint, parent=True):  # Find root joint
            print(f"🔍 Detected imported root joint: {joint}")
            return joint

    cmds.warning("⚠ No valid root joint found in new joints!")
    return None


def import_fbx_animation(fbx_file):
    """
    Imports an FBX animation into the Maya scene without duplicating the skeleton.
    """
    global imported_joint_uuids
    imported_joint_uuids.clear()  # Reset the list before each import

    if not os.path.exists(fbx_file):
        cmds.warning(f"⚠ FBX file does not exist: {fbx_file}")
        return None

    joints_before = cmds.ls(type="joint")  # Capture joints before import

    mel.eval('FBXImportMode -v "add";')  # Prevents skeleton duplication
    mel.eval(f'FBXImport -f "{fbx_file}";')
    print(f"✅ Animation successfully imported from: {fbx_file}")

    # Get newly imported joints
    imported_root_joint = get_new_root_joint(joints_before)
    imported_joints = cmds.ls(imported_root_joint, dag=True, type="joint") if imported_root_joint else []

    # Store UUIDs of imported joints
    for joint in imported_joints:
        selection = om.MSelectionList()
        try:
            selection.add(joint)
            obj = selection.getDependNode(0)
            uuid = str(om.MFnDependencyNode(obj).uuid())
            imported_joint_uuids.append(uuid)
        except:
            cmds.warning(f"⚠ Failed to get UUID for: {joint}")

    print(f"🔹 Imported Joint UUIDs: {imported_joint_uuids}")  # Debug print

    return imported_root_joint

# === TRANSFER ANIMATION: IMPORTED TO SOURCE ===
def transfer_animation(imported_root, rig_root):
    """
    Transfers animation from an imported skeleton to an existing rig.
    """
    if not cmds.objExists(imported_root) or not cmds.objExists(rig_root):
        cmds.warning("⚠ Imported or rig root not found. Skipping transfer.")
        return

    imported_joints = cmds.listRelatives(imported_root, allDescendents=True, type="joint", fullPath=True) or []
    rig_joints = cmds.listRelatives(rig_root, allDescendents=True, type="joint", fullPath=True) or []

    imported_joints.append(imported_root)
    rig_joints.append(rig_root)

    print(f"🔍 Imported skeleton has {len(imported_joints)} joints.")
    print(f"🔍 Target rig has {len(rig_joints)} joints.")

    imported_dict = {cmds.ls(j, long=True)[0].split("|")[-1]: j for j in imported_joints}
    rig_dict = {cmds.ls(j, long=True)[0].split("|")[-1]: j for j in rig_joints}

    if cmds.keyframe(imported_root, query=True, keyframeCount=True) > 0:
        print("🔹 Transferring root motion...")
        cmds.copyKey(imported_root)
        cmds.pasteKey(rig_root, option="replace")

    matched_count = 0
    for joint_name, imported_joint in imported_dict.items():
        if joint_name in rig_dict:
            rig_joint = rig_dict[joint_name]
            for attr in ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"]:
                if cmds.keyframe(imported_joint, attribute=attr, query=True, keyframeCount=True) > 0:
                    cmds.copyKey(imported_joint, attribute=attr)
                    cmds.pasteKey(rig_joint, attribute=attr, option="replace")
                    matched_count += 1

    print(f"✅ Successfully transferred animation for {matched_count} joints.")

# === TRANSFER ANIMATION: SOURCE TO TARGET (IGNORE NAMESPACES) ===
def remove_namespace(joint_name):
    """Removes the namespace from a joint name."""
    return joint_name.split(":")[-1]  

def transfer_animation_ignore_namespace(source_root, target_root):
    """
    Transfers animation from a source rig to a target rig, ignoring namespaces.
    """
    imported_joints = cmds.listRelatives(source_root, allDescendents=True, type="joint", fullPath=True) or []
    rig_joints = cmds.listRelatives(target_root, allDescendents=True, type="joint", fullPath=True) or []

    imported_joints.append(source_root)
    rig_joints.append(target_root)

    imported_dict = {remove_namespace(j): j for j in imported_joints}
    rig_dict = {remove_namespace(j): j for j in rig_joints}

    for joint_name, imported_joint in imported_dict.items():
        if joint_name in rig_dict:
            rig_joint = rig_dict[joint_name]
            for attr in ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"]:
                if cmds.keyframe(imported_joint, attribute=attr, query=True, keyframeCount=True) > 0:
                    cmds.copyKey(imported_joint, attribute=attr)
                    cmds.pasteKey(rig_joint, attribute=attr, option="replace")

    print("✅ Animation successfully transferred to target rig!")

    #EXPORT

def export_fbx_animation(rig_root, output_fbx_folder, animation_name, prefix="", suffix=""):
    """
    Exports an FBX file containing only the animation from the given rig.

    :param rig_root: The root joint of the rig to export.
    :param output_fbx_folder: The folder where the FBX file should be saved.
    :param prefix: (Optional) Prefix for the exported FBX file.
    :param suffix: (Optional) Suffix for the exported FBX file.
    """
    # Validate rig root
    if not cmds.objExists(rig_root):
        cmds.warning(f"⚠️ Rig root '{rig_root}' not found in the scene!")
        return
    
    # Get all joints in hierarchy
    export_joints = cmds.ls(rig_root, dag=True, type="joint")
    if not export_joints:
        cmds.warning(f"⚠️ No joints found under '{rig_root}'!")
        return

    cmds.select(export_joints, replace=True)

    # Ensure output folder exists
    output_fbx_folder = os.path.abspath(output_fbx_folder)  # Convert to absolute path
    if not os.path.exists(output_fbx_folder):
        try:
            os.makedirs(output_fbx_folder)
        except Exception as e:
            cmds.warning(f"⚠️ Failed to create export folder: {e}")
            return

    # Construct FBX filename
    rig_name = rig_root.replace(":", "_")  # Replace namespace colons
    output_fbx = os.path.join(output_fbx_folder, f"{prefix}{animation_name}{suffix}.fbx").replace("\\", "/")

    print(f"🔹 Exporting: {output_fbx}")

    # Ensure FBX plugin is loaded
    if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
        cmds.loadPlugin("fbxmaya")

    # Get timeline range
    start_frame = cmds.playbackOptions(query=True, minTime=True)
    end_frame = cmds.playbackOptions(query=True, maxTime=True)

    # ✅ Set FBX export settings for animation
    mel.eval('FBXExportConstraints -v false')
    mel.eval('FBXExportSkeletonDefinitions -v true')
    mel.eval('FBXExportSkins -v true')
    mel.eval('FBXExportAnimationOnly -v false')  # Allow skeleton export
    mel.eval('FBXExportBakeComplexAnimation -v true')
    mel.eval(f'FBXExportBakeComplexStart -v {start_frame}')
    mel.eval(f'FBXExportBakeComplexEnd -v {end_frame}')
    mel.eval('FBXExportBakeComplexStep -v 1')

    # ✅ Export the FBX
    try:
        mel.eval(f'FBXExport -f "{output_fbx}" -s')
        print(f"✅ Successfully exported: {output_fbx}")
    except Exception as e:
        cmds.warning(f"⚠️ FBX Export Failed: {e}")



def delete_imported_skeleton():
    """Deletes the imported skeleton using stored UUIDs, optimized to delete only the root joint."""
    global imported_joint_uuids

    print("\n🛠️ Starting delete_imported_skeleton()...")

    if not imported_joint_uuids:
        cmds.warning("⚠️ No imported joints found to delete!")
        return

    print(f"🔎 Found {len(imported_joint_uuids)} UUIDs to process.")

    # Get the first UUID only
    root_uuid = imported_joint_uuids[0]
    print(f"\n🔍 Processing only the root joint UUID: {root_uuid}")

    try:
        # Find the root joint by UUID
        node_name_list = cmds.ls(uuid=True)
        root_joint = None

        for node in node_name_list:
            if cmds.ls(node, uuid=True)[0] == root_uuid:
                root_joint = node
                break

        if not root_joint:
            print(f"❌ No root joint found for UUID {root_uuid}")
            return

        print(f"✅ Root joint identified: {root_joint}")

        # Unlock if necessary
        if cmds.lockNode(root_joint, query=True, lock=True)[0]:
            print(f"🔓 Unlocking {root_joint}...")
            cmds.lockNode(root_joint, lock=False)

        # Delete the root joint (which deletes the entire skeleton)
        print(f"🗑️ Deleting {root_joint} (this will remove all child joints too)...")
        cmds.delete(root_joint)

        # Confirm deletion
        if cmds.objExists(root_joint):
            print(f"❌ Failed to delete: {root_joint}")
        else:
            print(f"✅ Successfully deleted the skeleton!")

    except Exception as e:
        cmds.warning(f"⚠ Failed to delete skeleton. Error: {e}")

    # Clear UUID list since skeleton is deleted
    imported_joint_uuids.clear()
    print("✅ Finished delete_imported_skeleton().\n")
    


    
    

def batch_process_fbx(source_folder, export_folder, source_rig_root, target_rig_root, prefix="Anim_", suffix="_Final"):
    """
    Processes all FBX files in the source folder:
    1. Imports animation
    2. Transfers to source rig
    3. Transfers to target rig (ignoring namespaces)
    4. Exports final animation
    5. Deletes imported skeleton
    """
    if not os.path.exists(source_folder):
        print(f"⚠ Source folder does not exist: {source_folder}")
        return

    fbx_files = [f for f in os.listdir(source_folder) if f.lower().endswith('.fbx')]
    
    if not fbx_files:
        print("⚠ No FBX files found in the source folder.")
        return
    
    for fbx_file in fbx_files:
        fbx_file_path = os.path.join(source_folder, fbx_file).replace("\\", "/")
        animation_name = os.path.splitext(fbx_file)[0]
        print(f"🔹 Processing: {fbx_file_path}")

        imported_root_joint = import_fbx_animation(fbx_file_path)
        if imported_root_joint:
            transfer_animation(imported_root_joint, source_rig_root)
            transfer_animation_ignore_namespace(source_rig_root, target_rig_root)
            export_fbx_animation(target_rig_root, export_folder, animation_name, prefix=prefix, suffix=suffix)
            delete_imported_skeleton()
        else:
            print(f"⚠ Skipping {fbx_file}: No imported skeleton found.")

    print("✅ Batch processing complete!")  
    


# Global window name (prevents duplicates)
UI_WINDOW_NAME = "FBXBatchProcessorUI"

def show_fbx_batch_processor_ui():
    """Creates a UI for batch FBX processing with dropdowns for rig roots."""
    
    # Close existing UI if open
    if cmds.window(UI_WINDOW_NAME, exists=True):
        cmds.deleteUI(UI_WINDOW_NAME)

    # Create window
    window = cmds.window(UI_WINDOW_NAME, title="FBX Batch Processor", widthHeight=(500, 300), sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=5)

    # Source Folder
    cmds.text(label="Source Folder:")
    source_folder_field = cmds.textField()
    cmds.button(label="Browse", command=lambda _: set_folder(source_folder_field))

    # Target Folder
    cmds.text(label="Target Folder:")
    target_folder_field = cmds.textField()
    cmds.button(label="Browse", command=lambda _: set_folder(target_folder_field))

    # Source Rig Root Dropdown + Refresh
    cmds.text(label="Source Rig Root:")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(250, 50))
    source_rig_dropdown = cmds.optionMenu()
    cmds.button(label="↻", command=lambda _: populate_root_joints(source_rig_dropdown))
    cmds.setParent("..")  # Exit rowLayout

    # Target Rig Root Dropdown + Refresh
    cmds.text(label="Target Rig Root:")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(250, 50))
    target_rig_dropdown = cmds.optionMenu()
    cmds.button(label="↻", command=lambda _: populate_root_joints(target_rig_dropdown))
    cmds.setParent("..")  # Exit rowLayout

    # Prefix
    cmds.text(label="Prefix:")
    prefix_field = cmds.textField(text="Anim_")  # Default value

    # Suffix
    cmds.text(label="Suffix:")
    suffix_field = cmds.textField(text="_Final")  # Default value

    # Execute Button
    cmds.button(label="Execute Batch Process", bgc=(0.4, 0.8, 0.4), 
                command=lambda _: execute_batch_process(
                    cmds.textField(source_folder_field, query=True, text=True),
                    cmds.textField(target_folder_field, query=True, text=True),
                    cmds.optionMenu(source_rig_dropdown, query=True, value=True),
                    cmds.optionMenu(target_rig_dropdown, query=True, value=True),
                    cmds.textField(prefix_field, query=True, text=True),
                    cmds.textField(suffix_field, query=True, text=True)
                ))

    # Populate dropdowns initially
    populate_root_joints(source_rig_dropdown)
    populate_root_joints(target_rig_dropdown)

    cmds.showWindow(window)

def set_folder(text_field):
    """Opens a folder dialog and sets the selected folder path."""
    folder = cmds.fileDialog2(dialogStyle=2, fileMode=3)
    if folder:
        cmds.textField(text_field, edit=True, text=folder[0])

def populate_root_joints(dropdown):
    """Finds all root joints in the scene and updates the dropdown."""
    cmds.optionMenu(dropdown, edit=True, deleteAllItems=True)  # Clear existing items

    # Get all top-level joints (those without parents)
    root_joints = [jnt for jnt in cmds.ls(type="joint") if not cmds.listRelatives(jnt, parent=True)]

    if not root_joints:
        cmds.menuItem(label="No root joints found", parent=dropdown)
    else:
        for joint in root_joints:
            cmds.menuItem(label=joint, parent=dropdown)

def execute_batch_process(source_folder, export_folder, source_rig_root, target_rig_root, prefix, suffix):
    """Executes batch_process_fbx with UI inputs."""
    if not source_folder or not export_folder or not source_rig_root or not target_rig_root:
        cmds.warning("⚠️ Please fill in all required fields!")
        return

    print(f"🚀 Running batch_process_fbx with:")
    print(f"   Source Folder: {source_folder}")
    print(f"   Target Folder: {export_folder}")
    print(f"   Source Rig Root: {source_rig_root}")
    print(f"   Target Rig Root: {target_rig_root}")
    print(f"   Prefix: {prefix}")
    print(f"   Suffix: {suffix}")

    # Call the function with user inputs    
    
    batch_process_fbx(source_folder, export_folder, source_rig_root, target_rig_root, prefix, suffix)

# Automatically open the UI when script runs
show_fbx_batch_processor_ui()
 
###LAST UPDATE
 ##Added drop down for rig instead of text fields