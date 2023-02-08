import bpy
import sys
import ipdb
import os
from pathlib import Path
from bl_ui.space_text import TEXT_MT_editor_menus

repo_root_directory = os.path.join(os.path.dirname(__file__), ".")
sys.path.append(repo_root_directory)

argv = sys.argv[sys.argv.index("--") + 1:]
bpy.context.window.workspace = bpy.data.workspaces["Scripting"]
bpy.context.view_layer.update()
if argv[0].endswith(".py"):
    print(f"Loading: {os.path.join(os.path.dirname(os.path.abspath(__file__)), argv[0])}")
    text = bpy.data.texts.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), argv[0]))
    sys.argv = argv[:]
    print(f"New argv: {sys.argv}")
else:
    print("First argument should be the script file")
    exit(-1)

# Declare operator that runs the blender proc script
class RunHumanGeneratorOperator(bpy.types.Operator):
    bl_idname = "wm.run_humangenerator"
    bl_label = "Run Human Generator"
    bl_description = "This operator runs the loaded HumanGenerator script and also makes sure to unload all modules before starting."
    bl_options = {"REGISTER"}

    def execute(self, context):
        # Delete all loaded models inside src/, as they are cached inside blender
        for module in list(sys.modules.keys()):
            if module.startswith("humangenerator"):
                del sys.modules[module]

        # Make sure the parent of the humangenerator folder is in sys.path
        import_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
        if import_path not in sys.path:
            sys.path.append(import_path)

        # Run the script
        try:
            bpy.ops.text.run_script()
        except RuntimeError:
            # Skip irrelevant error messages (The relevant stacktrace+error has already been printed at this point)
            pass
        return {"FINISHED"}

bpy.utils.register_class(RunHumanGeneratorOperator)

def draw(self, context):
    layout = self.layout

    st = context.space_data
    text = st.text
    is_syntax_highlight_supported = st.is_syntax_highlight_supported()
    layout.template_header()

    TEXT_MT_editor_menus.draw_collapsible(context, layout)

    if text and text.is_modified:
        row = layout.row(align=True)
        row.alert = True
        row.operator("text.resolve_conflict", text="", icon='HELP')

    layout.separator_spacer()

    row = layout.row(align=True)
    row.template_ID(st, "text", new="text.new",
                    unlink="text.unlink", open="text.open")

    if text:
        is_osl = text.name.endswith((".osl", ".osl"))
        if is_osl:
            row.operator("node.shader_script_update",
                         text="", icon='FILE_REFRESH')
        else:
            row = layout.row()
            row.active = is_syntax_highlight_supported
            # The following line has changed compared to the orignal code, it starts our operator instead of text.run_script
            row.operator("wm.run_humangenerator", text="Run")

    layout.separator_spacer()

    row = layout.row(align=True)
    row.prop(st, "show_line_numbers", text="")
    row.prop(st, "show_word_wrap", text="")

    syntax = row.row(align=True)
    syntax.active = is_syntax_highlight_supported
    syntax.prop(st, "show_syntax_highlight", text="")

# Set our draw function as the default draw function for text area headers
bpy.types.TEXT_HT_header.draw = draw

# Put text into scripting tool
for area in bpy.data.workspaces["Scripting"].screens[0].areas.values():
    if area.type == 'TEXT_EDITOR':
        area.spaces.active.text = text