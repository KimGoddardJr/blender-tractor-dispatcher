
# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

'''
DESCRIPTION
Tractor Dispatcher is a simple tool for dispatching jobs to a render farm managed by Pixar's Tractor render manager.

See http://ragnarb.com/tractor-dispatcher-for-blender for docs.

WARNING!
This script is only tested on Linux, but should work on OSX too. It likely won't work on Windows, though you never know.
Prior to version 2.65 of Blender, this plug-in will break Cycles texture paths in your scene. This means that after you dispatch your scene to the farm, you need to reload it. This is due to bug #33108  ( http://projects.blender.org/tracker/index.php?func=detail&aid=33108&group_id=9&atid=498 ).
'''

bl_info = {
    "name": "Tractor Dispatcher",
    "author": "Ragnar Brynjulfsson, Jean The First, King Goddard Jr",
    "version": (1, 0, 0),
    "blender": (2, 90, 0),
    "location": "Properties > Render > Tractor Dispatcher",
    "description": "Dispatch jobs to Pixar's Tractor render farm manager ",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/Render/Tractor_Dispatcher_for_Blender",
    "tracker_url": "",
    "category": "Render"}


if "bpy" in locals():
	import importlib
	if "tractor_render_dispatcher" in locals():
		importlib.reload(tractor_render_dispatcher)


import bpy
from bpy.app.handlers import persistent
#import script files
from . import tractor_render_dispatcher



def register():
	tractor_render_dispatcher.register()


def unregister():
	tractor_render_dispatcher.unregister()


if __name__ == "__main__":
	register()