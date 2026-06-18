from imgui_bundle import imgui;
from ee_assets import AssetManager, AssetDocument, DocumentHelper;
from ee_sprites import SpritePreview;
import ee_types;
from ee_tool_window import ToolWindow, ToolWindowRegistry;
from ee_asset_explorer import AssetExplorer;
from ee_file_explorer import FileExplorer;
from ee_imgui import *;
import copy;

class DocumentEditor:
	def render(doc : AssetDocument):
		for instance in doc.instances:
			eegui_typed_input(
				id(instance),
				doc.type_helper.abstract_tree.T, instance,
				pretty=True
			);