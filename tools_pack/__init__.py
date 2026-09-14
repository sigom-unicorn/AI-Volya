# C:\ai_volya\tools_pack\__init__.py
from .web_tools import search_online, browse_website
from .file_tools import read_app_file, write_app_file, create_app_folder, list_app_dir, delete_app_object, copy_app_file
from .db_manager import execute_raw_sql
from .game_tools import launch_quest, setup_veche_circle_and_open_voting, record_vote, close_veche_and_apply_decision

all_tools = [
    search_online,
    browse_website,
    read_app_file,
    write_app_file,
    create_app_folder,
    list_app_dir,
    delete_app_object,
    copy_app_file,
    execute_raw_sql,
    launch_quest,
    setup_veche_circle_and_open_voting,
    record_vote,
    close_veche_and_apply_decision
]

db_tools = [execute_raw_sql]
game_tools = [launch_quest, setup_veche_circle_and_open_voting, record_vote, close_veche_and_apply_decision]
