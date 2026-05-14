from imgui_bundle import imgui;
from ee_assets import AssetManager, AssetDocument, DocumentHelper;
from ee_sprites import SpritePreview;
import ee_types;
from ee_tool_window import ToolWindow, ToolWindowRegistry;
from ee_asset_explorer import AssetExplorer;
from ee_file_explorer import FileExplorer;
from ee_imgui import *;

class DocumentEditor:
	_search_term = "";
	_search_subset = [];

	_delete_queue = [];
	_duplicate_queue = [];
	
	def _render_node(title, T, node, entry_id):		
		if isinstance(T, ee_types.Object):
			object_open = imgui.tree_node(f"{title}####{entry_id}");
			
			if imgui.begin_popup_context_item():
				if imgui.menu_item_simple("Delete"):
					DocumentEditor._delete_queue.append(node);
				if imgui.menu_item_simple("Duplicate"):
					DocumentEditor._duplicate_queue.append(node);
				imgui.end_popup();
			
			if object_open:
				if AssetManager.active_document.type == "sprite":
					SpritePreview.draw(node["name"]);
				for e in T.elements:
					if e.name in node:
						if not e.get_attribute("read-only"):
							node[e.name] = DocumentEditor._render_node(e.name, e.T, node[e.name], entry_id);
				imgui.tree_pop();
			return node;
		
		elif isinstance(T, ee_types.List):
			if imgui.tree_node(title):
				for i in range(len(node)):
					node[i] = DocumentEditor._render_node(f"{title}[{i}]", T.T, node[i], entry_id);
				imgui.tree_pop();
				if imgui.button("+"):
					node.append(T.T.prototype());
			return node;
		
		elif isinstance(T, ee_types.Asset):
			if T.name == "sprite":
				SpritePreview.draw(node);

			imgui.text(title);
			imgui.same_line();
			
			if T.name in AssetManager.types():
				return imgui_asset_input(f"##{title}", T.name, node);
			else:
				_, result = imgui.input_text(f"##{title}", str(node));
				return result;
		
		elif isinstance(T, ee_types.File):
			imgui.text(title);
			imgui.same_line();

			_, result = imgui.input_text(f"##{title}", str(node));
			imgui.same_line();
			explorer = ToolWindowRegistry.lookup(FileExplorer);
			if imgui.button(f"...##{title}") and not explorer.is_open():
				explorer.open();
				explorer.get().configure(node, AssetManager.active_document.directory, T.pattern, "sprite" if AssetManager.active_document.type == "sprite" else None);
			if explorer.is_open() and explorer.get().is_targeting(node):
				harvest = explorer.get_result();
				result = harvest if harvest != None else result;
			return result;

		elif isinstance(T, ee_types.Enum):
			imgui.text(title);
			imgui.same_line();

			result = node;
			if imgui.begin_combo(f"##{title}", result):
				for item in T.values:
					selected = result == item;
					if imgui.selectable(item, selected)[0]:
						result = item;
					if selected:
						imgui.set_item_default_focus();	
				imgui.end_combo();
			return result;

		elif isinstance(T, ee_types.Flags):
			imgui.text(title);

			result = node;
			for value in T.values:
				_, included = imgui.checkbox(value, value in result);
				if included and not value in result:
					result.append(value);
				elif not included and value in result:
					result.remove(value);
			return result;

		elif isinstance(T, ee_types.Primitive):
			imgui.text(title);
			imgui.same_line();
			
			match type(T):
				case ee_types.Int:
					_, result = imgui.input_int(f"##{title}", int(node));
					return result;
				case ee_types.Float:
					_, result = imgui.input_float(f"##{title}", float(node));
					return result;
				case ee_types.Bool:
					return imgui.checkbox(f"##{title}", bool(node))[1];
				case ee_types.String:
					_, result = imgui.input_text(f"##{title}", str(node));
					return result;
	
	def render(doc : AssetDocument):
		search_changed, DocumentEditor._search_term = imgui.input_text("Search", DocumentEditor._search_term);
		if search_changed:
			DocumentEditor._search_subset = list(filter(lambda e: DocumentEditor._search_term in e["name"], doc.instances));
		working_set = DocumentEditor._search_subset if len(DocumentEditor._search_term) > 0 else doc.instances;

		for entry in working_set:
			root = doc.typist.root();

			name = DocumentHelper.get_name(entry);
			number = DocumentHelper.get_number(entry);
			DocumentEditor._render_node(f"{name} {number}", root.T, entry, str(id(entry)));

		while len(DocumentEditor._duplicate_queue) > 0:
			x = DocumentEditor._duplicate_queue.pop(0);
			AssetManager.active_document.duplicate_entry(x);
		while len(DocumentEditor._delete_queue) > 0:
			x = DocumentEditor._delete_queue.pop(0);
			AssetManager.active_document.delete_entry(x);
		