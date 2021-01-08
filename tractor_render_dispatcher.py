import bpy
from bpy.props import IntProperty, StringProperty, BoolProperty, FloatProperty, EnumProperty

import os
import sys
import subprocess
from time import gmtime, strftime, sleep
from tempfile import gettempdir
from shutil import copy2

from math import ceil

from . submitter import TrHttpRPC, Spool, trAbsPath, jobSpool

## ------------------------------------------------------------- ##
sys.path.insert(1, os.path.join(sys.path[0], "blade-modules"))
## ------------------------------------------------------------- ##

tractorblade_options = [
    ("ALL", "All GPUs",   'All Blades', 0),
    ("D300", "D300 GPUs", 'Blades with D300 GPU', 1),
    ("D500", "D500 GPUs", 'Blades with D500 GPU', 2),
]

# properties
bpy.types.Scene.tractordispacher_dorender = BoolProperty(
    name="Render Scene",
    description="Render the scene using current render settings",
    default=True
    )

bpy.types.Scene.tractordispacher_showprogress = BoolProperty(
    name="Show Progress",
    description="Show per frame progress (only works on Linux or OSX with Cycles or Blender Internal renderer)",
    default=True
    )

bpy.types.Scene.tractordispacher_priority = FloatProperty(
    name="Priority",
    description="Priority in the tractor job queue",
    min = 0.0, max = 1000000.0,
    default = 1.0
    )

bpy.types.Scene.tractordispacher_framesperunit = IntProperty(
    name="Frames per Unit",
    description="Frames per Unit",
    min = 1, max = 10000,
    default = 1
    )

bpy.types.Scene.tractordispacher_blade = EnumProperty(
    name="Blade",
    items=tractorblade_options,
    description="Blades",
    default="ALL",
    )

bpy.types.Scene.tractordispacher_crews = StringProperty(
    name="Crews",
    description="Comma seperated list of crews to use",
    maxlen=4096,
    default=""
    )

bpy.types.Scene.tractordispacher_tags = StringProperty(
    name="Tags",
    description="Space seperated list of tags to use",
    maxlen=4096,
    default=""
    )

bpy.types.Scene.tractordispacher_envkey = StringProperty(
    name="Envkey",
    description="Arbitrary key passed to the remote machine, used by AlfEnvConfig",
    maxlen=4096,
    default=""
    )

bpy.types.Scene.tractordispacher_prescript = StringProperty(
    name="Pre-Script",
    description="Optional script file to run before the job starts",
    maxlen=4096,
    subtype='FILE_PATH'
    )

bpy.types.Scene.tractordispacher_postscript = StringProperty(
    name="Post-Script",
    description="Optional script file to run after the job is done",
    maxlen=4096,
    subtype='FILE_PATH'
    )
'''
bpy.types.Scene.tractordispacher_spool = StringProperty(
    name="Spool Path",
    description="Path to where temporary files are stored (.alf script and .blend file)",
    maxlen=4096,
    default=gettempdir(),
    subtype='DIR_PATH'
    )
'''
bpy.types.Scene.tractordispacher_usebinarypath = BoolProperty(
    name="Use Full Binary Path",
    description="Use the full path to the Blender executable (check when using multiple versions of Blender)",
    default=False
    )


class TractorDispatcherPanel(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "Tractor Dispatcher"
    bl_idname = "OBJECT_PT_tractor"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"


    def draw(self, context):

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        obj = bpy.context.active_object
        sce = bpy.context.scene

        row = layout.row()
        row.prop(sce, "tractordispacher_dorender")
        row.prop(sce, "tractordispacher_showprogress")

        box = layout.box()
        col = box.column(align=True)
        col.prop(sce, "frame_start", text="Frame Start")
        col.prop(sce, "frame_end", text="End")
        col.prop(sce, "frame_step", text="Step")


        box = layout.box()
        row = box.row()
        row.prop(sce, "tractordispacher_priority")

        row = box.row()
        row.prop(sce, "tractordispacher_framesperunit")

        row = box.row()
        row.prop(sce, "tractordispacher_blade")

        row = layout.row()
        row.prop(sce, "tractordispacher_crews")
        row = layout.row()
        row.prop(sce, "tractordispacher_tags")
        row = layout.row()
        row.prop(sce, "tractordispacher_envkey")

        row = layout.row()
        row.prop(sce, "tractordispacher_prescript")
        row = layout.row()
        row.prop(sce, "tractordispacher_postscript")

        #row = layout.row()
        #row.prop(sce, "tractordispacher_spool")

        row = layout.row()
        row.prop(sce, "tractordispacher_usebinarypath")

        row = layout.row()
        row.operator("tractordispacher.button", text="Dispatch Job")


class TRACTORDISPACHER_OT_Button(bpy.types.Operator):
    bl_idname = "tractordispacher.button"
    bl_label = "Button"
    bl_description = "Dispatch scene to tractor blades"
    mode: IntProperty(name="mode", default=1)

    def now(self):
        # Returns preformated time for now.
        return strftime("%H%M%S", gmtime())

    def spoolJob(self):

        ##### TRACTOR VARIABLES ######
        ##private variables
        self.tractorEngineName = '10.180.128.13'
        self.tractorEnginePort = 8080
        if 'TRACTOR_ENGINE' in os.environ.keys():
            name = os.environ['TRACTOR_ENGINE']
            self.tractorEngineName,n,p = name.partition( ":" )
            if p:
                self.tractorEnginePort = int( p )
        ##public variables

        self.tractorEngine = '' + str( self.tractorEngineName ) + ':' + str( self.tractorEnginePort )

        jobScript = self.createJobScript()
        args = []
        args.append('--engine=' + self.tractorEngine)
        #if self.doJobPause:
        #    args.append('--paused')
        args.append(jobScript)

        Spool(args)

    def createJobScript(self):

        # Dispatch the job to tractor.
        # Spool out the blender file.
        spooledfiles = []
        spooldirname = os.path.dirname(bpy.data.filepath)
        #if not os.path.exists(bpy.context.scene.tractordispacher_spool):
        #    os.makedirs(bpy.context.scene.tractordispacher_spool)
        if not os.path.exists(spooldirname):
            os.makedirs(spooldirname)
        basefilename = os.path.basename(os.path.splitext(bpy.data.filepath)[0])
        blendshort = "{}_{}.blend".format(basefilename, self.now())
        #blendfull = os.path.join(bpy.context.scene.tractordispacher_spool, blendshort)
        blendfull = os.path.join(spooldirname, blendshort)
        bpy.ops.wm.save_as_mainfile(filepath=blendfull, copy=True, relative_remap=True)
        spooledfiles.append(blendfull)
        # Create the .alf script.
        blender_binary = "blender"
        if bpy.context.scene.tractordispacher_usebinarypath:
            blender_binary = bpy.app.binary_path
        jobshort = "{}_{}.alf".format(basefilename, self.now())
        #jobfull = os.path.join(bpy.context.scene.tractordispacher_spool, jobshort)
        jobfull = os.path.join(spooldirname, jobshort)
        self.file = open(jobfull, 'w')
        spooledfiles.append(jobfull)

        envkey = "TOOLS={} {}".format(os.environ.get('TOOLS'), bpy.context.scene.tractordispacher_envkey)
        addons = ",".join(bpy.context.preferences.addons.keys())
        blender_user_scripts = os.environ.get('BLENDER_USER_SCRIPTS')

        if bpy.context.scene.tractordispacher_blade == 'D300':
            service = 'BlenderRenderD300'
        elif bpy.context.scene.tractordispacher_blade == 'D500':
            service = 'BlenderRenderD500'
        else:
            service = 'BlenderRender'

        self.file.write("Job -title {{{}}}".format(blendshort))
        #self.file.write(" -pbias {} ".format(bpy.context.scene.tractordispacher_priority))
        self.file.write(" -priority {}".format(bpy.context.scene.tractordispacher_priority))
        self.file.write(" -tags {{ Blender {} }}".format(bpy.context.scene.tractordispacher_tags))
        #self.file.write(" -service {BlenderRender}")
        self.file.write(" -service {{ {} }}".format(service))
        self.file.write(" -crews {{{}}}".format(bpy.context.scene.tractordispacher_crews))
        #self.file.write(" -projects ".format(bpy.context.scene.tractordispacher_projects))
        self.file.write(" -projects Default")
        self.file.write(" -envkey {{{}}}".format(envkey))
        #self.file.write(" -whendone {{{}}}".format(bpy.context.scene.tractordispacher_jobDoneCmd))
        #self.file.write(" -whenerror {{{}}}".format(bpy.context.scene.tractordispacher_jobErrorCmd))
        #self.file.write(" {} ".format(bpy.context.scene.tractordispacher_extraJobOptions)
        self.file.write(" -serialsubtasks 1")
        self.file.write(" -subtasks {\n")

        # Run pre-script
        if bpy.context.scene.tractordispacher_prescript:
            #prefull = os.path.join(bpy.context.scene.tractordispacher_spool, "{}_{}_pre.py" .format( basefilename, self.now() ))
            prefull = os.path.join(spooldirname, "{}_{}_pre.py" .format( basefilename, self.now() ))
            copy2(bpy.path.abspath(bpy.context.scene.tractordispacher_prescript), prefull )
            self.file.write("    Task {Pre-Job Script} -cmds {\n")
            self.file.write("        RemoteCmd {{{} --background {} --python {}}}\n".format( blender_binary, blendfull, prefull ))
            self.file.write("    }\n")
            spooledfiles.append(prefull)

        # Render frames
        bashwrap=""
        progresscmd=" "
        if bpy.context.scene.tractordispacher_showprogress:
            if bpy.context.scene.render.engine == 'BLENDER_EEVEE':
                bashwrap="/bin/bash -c {"
                progresscmd=" | while read line;do echo \$line;echo \$line | grep 'Rendering' | awk {'print 100 / $(NF-1) * $(NF-3)'} | cut -d. -f1 | sed 's/^/TR_PROGRESS /;s/\$/%/';done}"
            # BLENDER_WORKBENCH has no progress
            #if bpy.context.scene.render.engine == 'BLENDER_WORKBENCH':
            #    bashwrap="/bin/bash -c {"
            #    progresscmd=" | while read line;do echo \$line;echo \$line | grep 'Scene, Part' | awk {'print \$(NF)'} | sed 's/-/\\\//g' | sed 's/$/*100/' | bc -l | cut -d. -f1| sed 's/^/TR_PROGRESS /;s/\$/%/';done}"
            if bpy.context.scene.render.engine == 'CYCLES':
                bashwrap="/bin/bash -c {"
                progresscmd=" | while read line;do echo \$line;echo \$line | grep 'Rendered' | awk {'print \$(NF-1)'} | sed 's/$/*100/' | bc -l | cut -d. -f1 | sed 's/^/TR_PROGRESS /;s/\$/%/';done}"
        if bpy.context.scene.tractordispacher_dorender:
            self.file.write("    Task {Render Frames} -subtasks {\n")

            start = bpy.context.scene.frame_start
            end = bpy.context.scene.frame_end
            step = bpy.context.scene.frame_step

            fpu = bpy.context.scene.tractordispacher_framesperunit

            s = start
            e = s + step * fpu - 1

            #for f in range(start,end,step):
            while s < end:
                #print("s:{} e:{} s:{}".format(s,e,step))  
                e = min(e, end)

                title = "Frame {}".format(s) if s == e else "Frame {} - {}".format(s, e)

                self.file.write("        Task {{ {} }} -cmds {{\n".format(title))
                self.file.write("            RemoteCmd {{{}{} --background --factory-startup -y {} --python {}/init.py --frame-start {} --frame-end {} --frame-jump {} --render-anim -- -e {} {} }} -service {{ {} }} -envkey {{ {} }} -tags {{ Blender {} }}\n".format( bashwrap, blender_binary, blendfull, blender_user_scripts, s, e, step, addons, progresscmd, service, envkey, bpy.context.scene.tractordispacher_tags ))
                self.file.write("        }\n")

                s = e + 1
                e = s + step * fpu - 1

            self.file.write("    }\n")

        # Run post-script
        if bpy.context.scene.tractordispacher_postscript:
            #postfull = os.path.join(bpy.context.scene.tractordispacher_spool, "{}_{}_post.py".format( basefilename, self.now() ))
            postfull = os.path.join(spooldirname, "{}_{}_post.py".format( basefilename, self.now() ))
            copy2(bpy.path.abspath(bpy.context.scene.tractordispacher_postscript), postfull )
            self.file.write("    Task {Post-Script} -cmds {\n")
            self.file.write("        RemoteCmd {{{} --background {} --python {}}}\n".format( blender_binary, blendfull, bpy.context.scene.tractordispacher_postscript ))
            self.file.write("    }\n")
            spooledfiles.append(postfull)

        self.file.write("}\n")
        self.file.close()

        # Just to make doubly sure the .alf script is available on disk.
        sleep(1)
        # Python based Job to Tractor Dispatcher
        """
        tractor_host = os.environ.get('TRACTOR_HOST')
        tractor_port = os.environ.get('TRACTOR_PORT')
        command = "tractor-spool --engine={}:{} {}".format(tractor_host, tractor_port, jobfull)
        if subprocess.call([ command, jobfull ], shell=True) != 0:
            raise RuntimeError("Failed to run tractor-spool, check that it's in path. The spooled files were still written out to {}".format( bpy.context.scene.tractordispacher_spool ))
        """
        return jobfull

    def execute(self, context):

        self.spoolJob()

        return{'FINISHED'}


def register():
    bpy.utils.register_class(TRACTORDISPACHER_OT_Button)
    bpy.utils.register_class(TractorDispatcherPanel)


def unregister():
    bpy.utils.unregister_class(TRACTORDISPACHER_OT_Button)
    bpy.utils.unregister_class(TractorDispatcherPanel)


if __name__ == "__main__":
    register()


'''
********
* NEXT *
********
- Test if sleep is needed.

*********
* TODO! *
*********
- Catch errors when jobs fail to dispatch.
- Combine Blur pass with progress to get a non-repeating progressbar when rendering with Blender Internal render and motion blur.
- Add support for easily baking simulations that don't require th

*********
* NOTES *
*********
- Pre- and post frame scripts can simply use, bpy.app.handlers.render_post/pre in the file.
- Saving your spooled files in your pre script.
-- bpy.ops.wm.save_mainfile(filepath=bpy.data.filepath)

***************
* LIMITATIONS *
***************
- Not tested on Windows and OSX. While I've tried making everything as os independent as possible, I don't have access to a farm running on Windows or OSX. OSX will likely work, but for Windows you'll have to disable the progress display as it uses *nix tools to convert the render output log to percentages.
- Only tested with Cycles and Blender internal renderer. If trying to use it with other renders you need to uncheck Show Progress. The renderer should also be launched with the same standard command line used for launching blender internal or cycles renderer.
- The progress bar for each frame works incorrectly when using motion blur in the internal render. It will go from zero to full for each pass, rather than for the whole frame.
'''
