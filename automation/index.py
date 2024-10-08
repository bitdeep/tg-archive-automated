import os
import json
import re
import shutil
import time
import subprocess
import asyncio
import colorama
import humanize
import traceback

from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from datetime import datetime
colorama.init(strip=False, autoreset=True)

def print_cyan(group, message, start_time=None):
    print(get_log_id(group, start_time) + colorama.Fore.CYAN + message + colorama.Fore.RESET)

def print_green(group, message, start_time=None):
    print(get_log_id(group, start_time) + colorama.Fore.GREEN + message + colorama.Fore.RESET)

def print_red(group, message, start_time=None):
    print(get_log_id(group, start_time) + colorama.Fore.RED + message + colorama.Fore.RESET)

def print_yellow(group, message, start_time=None):
    print(get_log_id(group, start_time) + colorama.Fore.YELLOW + message + colorama.Fore.RESET)

# Load API credentials from .env file
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
SESSION_ID = os.getenv('SESSION_ID', 'session.session')
SESSION_PATH = f'/session/{SESSION_ID}'
# Path for the cache file
CACHE_FILE = '/data/index.json'
# Your own username or phone number will be set dynamically
MY_USERNAME = None

async def get_my_username():
    global MY_USERNAME
    async with TelegramClient(SESSION_ID, API_ID, API_HASH) as client:
        me = await client.get_me()
        MY_USERNAME = me.username if me.username else me.phone
    return MY_USERNAME

def parse_group_name(name):
    # Remove non-ASCII characters and replace spaces with underscores
    parsed_name = re.sub(r'[^\x00-\x7F]+', '', name)
    parsed_name = re.sub(r'\s+', '_', parsed_name)
    parsed_name = re.sub(r'[^a-zA-Z0-9\-_\.]', '', parsed_name)
    parsed_name = parsed_name.lower()
    return parsed_name.strip('_')

def create_group_directory(group_name, group_id):
    parsed_name = parse_group_name(group_name)
    dir_path = os.path.join('/data', parsed_name)
    os.makedirs(dir_path, exist_ok=True)
    
    # Copy and modify config.yaml
    config_src = '/app/mysite/config.yaml'
    config_dest = os.path.join(dir_path, 'config.yaml')
    with open(config_src, 'r') as src_file, open(config_dest, 'w') as dest_file:
        config_content = src_file.read()
        config_content = config_content.replace('--GROUP-ID--', str(group_id))
        config_content = config_content.replace('--ID--', str(API_ID))
        config_content = config_content.replace('--HASH--', str(API_HASH))
        dest_file.write(config_content)
    
    # Create static directory and copy template.html
    static_dir = os.path.join(dir_path, 'static')
    os.makedirs(static_dir, exist_ok=True)
    template_src = '/app/mysite/template.html'
    template_dest = os.path.join(dir_path, 'template.html')
    shutil.copy(template_src, template_dest)
    
    return dir_path

async def get_groups():
    async with TelegramClient(SESSION_ID, API_ID, API_HASH) as client:
        dialogs = await client.get_dialogs(archived=False, ignore_pinned=True, ignore_migrated=True)
        groups = []
        print(colorama.Fore.CYAN + f"Total dialogs fetched: {len(dialogs)}" + colorama.Fore.RESET)
        i=0
        for d in dialogs:
            if not isinstance(d.entity, (Channel, Chat)):
                continue
            # Check if the group is archived, if so, skip it
            if d.entity.left:
                print(colorama.Fore.RED + f"Skipping archived group: {d.name}" + colorama.Fore.RESET)
                continue
            type = 'channel' if isinstance(d.entity, Channel) else 'group'
            print(colorama.Fore.CYAN + f"[{i}] t.me/{d.name} ({type})" + colorama.Fore.RESET)
            i+=1
            group_dir = create_group_directory(d.name, d.entity.id)
            groups.append({
                'id': d.entity.id,
                'name': d.name,
                'type': type,
                'directory': group_dir
            })
        
        return groups

def cache_groups(groups):
    with open(CACHE_FILE, 'w') as f:
        json.dump(groups, f, indent=2)

import time

def load_cached_groups():
    if os.path.exists(CACHE_FILE):
        cache_age = time.time() - os.path.getmtime(CACHE_FILE)
        if cache_age < 86400:  # 86400 seconds = 1 day
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
    return None

def bytes_to_human(size):
    return humanize.naturalsize(size, binary=True)

colorama.init(strip=False, autoreset=True)

def get_log_id(group, start_time=None):
    if start_time:
        time_passed = datetime.now() - start_time
        humanized_time = humanize.naturaldelta(time_passed)
    else:
        humanized_time = '-'
    id = group['id'] if isinstance(group, dict) else '-'
    name = group['name'] if isinstance(group, dict) else '-'
    log_id = (
        (f"{colorama.Fore.CYAN}🕒 {humanized_time} {colorama.Fore.RESET} " if humanized_time != '-' else '') +
        (f"{colorama.Fore.GREEN}🆔 {id} {colorama.Fore.RESET} " if id != 0 else '') +
        (f"{colorama.Fore.BLUE}📁 {name} {colorama.Fore.RESET} " if name != 'System' else '')
    )
    return log_id



def show_process_stats(group, process, start_time, operation):
    while process.poll() is None:
        time.sleep(60)  # Wait for 1 minute
        dir_size = get_directory_size(group['directory'])
        total, used, free = shutil.disk_usage("/data")
        free_percent = (free / total) * 100
        used_percent = 100 - free_percent
        space_color = colorama.Fore.RED if used_percent >= 90 else colorama.Fore.YELLOW

        # Disk space info line
        disk_info = (
            f"{colorama.Fore.CYAN}💾 Disk:{colorama.Fore.RESET} "
            f"Total: {bytes_to_human(total)} | "
            f"Used: {bytes_to_human(used)} ({used_percent:.1f}%) | "
            f"{space_color}Free: {bytes_to_human(free)} ({free_percent:.1f}%){colorama.Fore.RESET}"
        )
        print_yellow(group, disk_info)

        # Status message and time info line
        time_passed = datetime.now() - start_time
        status_message = (
            f"{colorama.Fore.YELLOW}📊 Status:{colorama.Fore.RESET} "
            f"{operation.capitalize()} in progress | "
            f"{colorama.Fore.GREEN}📁 Size: {bytes_to_human(dir_size)}{colorama.Fore.RESET} | "
            f"{colorama.Fore.MAGENTA}⏱️ Time: {humanize.naturaldelta(time_passed)}{colorama.Fore.RESET}"
        )
        print_yellow(group, status_message)

    process.wait()
    completion_message = f"{colorama.Fore.GREEN}✅ [{operation.upper()}] COMPLETED with returncode: {process.returncode}{colorama.Fore.RESET}"
    print_green(group, completion_message)
    return process.returncode

def run_tg_archive(group):
    group_id = group['id']
    group_dir = group['directory']
    os.chdir(group_dir)
    start_time = datetime.now()
    config_path = os.path.join(group_dir, 'config.yaml')
    data_path = os.path.join(group_dir, 'data.sqlite')
    template = os.path.join(group_dir, 'template.html')
    base_command = ['/usr/local/bin/tg-archive', 
                    '--symlink', 
                    '--config', config_path, 
                    '--data', data_path, 
                    '--path', group_dir, 
                    '--session', SESSION_PATH,
                    '--template', template
                    ]
    sync_command = base_command + ['--sync']
    build_command = base_command + ['--build']
    try:
        group_size = os.path.getsize(data_path) if os.path.exists(data_path) else 0
        print_cyan(group, f"size: {bytes_to_human(group_size)}, dir {group_dir}", None)
        print_cyan(group, ' '.join(sync_command), None)
        process = subprocess.Popen(sync_command, cwd=group_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        returncode = show_process_stats(group, process, start_time, "sync")
        if returncode == 0:
            print_green(group, f"Successfully ran tg-archive sync for group {group_id}", start_time)
            print_green(group, ' '.join(build_command), start_time)
            process = subprocess.Popen(build_command, cwd=group_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            returncode = show_process_stats(group, process, start_time, "build")
            if returncode == 0: print_green(group, f"Successfully ran tg-archive build for group {group_id}", start_time)
            else: print_red(group, f"ERR-2 running tg-archive build for group {group_id}", start_time)
            final_size = os.path.getsize(data_path)
            print_cyan(group, f"Finished processing group {group_id} (Final size: {bytes_to_human(final_size)})", start_time)
        else:
            print_red(group, f"ERR-1 running tg-archive sync for group {group_id}", start_time)
    except Exception as e:
        print_red(group, str(e), start_time)
        traceback.print_exc()
        time.sleep(60000000)

def get_directory_size(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

def load_template(template_name):
    with open(os.path.join('/app', 'templates', template_name), 'r') as f:
        return f.read()

def generate_index_html(groups):
    index_template = load_template('index_template.html')
    group_item_template = load_template('group_item_template.html')
    
    group_list = []
    for group in groups:
        group_name = group['name']
        group_dir = os.path.basename(group['directory'])
        group_type = group['type'].capitalize()
        index_file = os.path.join(group['directory'], 'index.html')
        if os.path.exists(index_file):
            last_modified = datetime.fromtimestamp(os.path.getmtime(index_file))
            last_modified_str = last_modified.strftime("%Y-%m-%d %H:%M:%S")
            dir_size = get_directory_size(group['directory'])
            dir_size_str = humanize.naturalsize(dir_size, binary=True)
            group_list.append(group_item_template.format(
                group_dir=group_dir,
                group_name=group_name,
                group_type=group_type,
                last_modified_str=last_modified_str,
                dir_size_str=dir_size_str
            ))
    
    try:
        html_content = index_template.format(group_list='\n'.join(group_list))
    except KeyError as e:
        print_red({'id': 0, 'name': 'System'}, f"Error formatting index template: {str(e)}")
        print_red({'id': 0, 'name': 'System'}, "Check if all placeholders in the template are correctly filled.")
        html_content = "<html><body><h1>Error generating index</h1><p>Please check the logs for more information.</p></body></html>"
    
    with open('/data/index.html', 'w') as f:
        f.write(html_content)

async def process_groups():
    global MY_USERNAME
    if MY_USERNAME is None:
        MY_USERNAME = await get_my_username()
        print_green({'id': 0, 'name': 'System'}, f"Detected username: {MY_USERNAME}")
    
    groups = await get_groups()
    cache_groups(groups)
    total_groups = len(groups)
    start_time = time.time()
    print_cyan({'id': 0, 'name': 'System'}, f"Started processing groups at: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}")
    
    processing_times = []
    for index, group in enumerate(groups, start=1):
        group_start_time = time.time()
        dir_size = get_directory_size(group['directory'])
        print("\n---\n")
        progress_percentage = (index / total_groups) * 100
        print_cyan({'id': 0, 'name': 'System'}, f"Progress: {progress_percentage:.2f}% ({index}/{total_groups})")
        print_cyan(group, f"Type: {group['type']}, Size: {bytes_to_human(dir_size)}")
        run_tg_archive(group)
        group_end_time = time.time()
        group_processing_time = group_end_time - group_start_time
        processing_times.append(group_processing_time)
        avg_time = sum(processing_times) / len(processing_times)
        remaining_groups = total_groups - index
        estimated_completion_time = avg_time * remaining_groups
        end_time = time.time()
        total_time = end_time - start_time
        avg_time = sum(processing_times) / len(processing_times)
        print_cyan(group, f"Time taken to process this group: {humanize.naturaldelta(group_processing_time)}")
        print_cyan(group, f"Average processing time: {humanize.naturaldelta(avg_time)}")
        print_cyan(group, f"Estimated time to complete all groups: {humanize.naturaldelta(estimated_completion_time)}")
        generate_index_html(groups)
        
    print_cyan({'id': 0, 'name': 'System'}, f"\nTotal groups processed: {total_groups}")
    print_cyan({'id': 0, 'name': 'System'}, f"Total time taken: {humanize.naturaldelta(total_time)}")
    print_cyan({'id': 0, 'name': 'System'}, f"Average time per group: {humanize.naturaldelta(avg_time)}")
    


def run_periodically(interval, func, *args, **kwargs):
    while True:
        func(*args, **kwargs)
        time.sleep(interval)

def gen_session_config():
    config_src = '/app/mysite/config.yaml'
    with open(config_src, 'r') as src_file:
        config_content = src_file.read()
        config_content = config_content.replace('--GROUP-ID--', str(1))
        config_content = config_content.replace('--ID--', str(API_ID))
        config_content = config_content.replace('--HASH--', str(API_HASH))
    return config_content

def check_session():
    print(f'SESSION_PATH: {SESSION_PATH}')
    os.chdir('/session')
    config_path = os.path.join('/session', 'config.yaml')
    config_content = gen_session_config()
    with open(config_path, 'w') as f:
        f.write(config_content)
    if not os.path.exists(SESSION_PATH):
        print_red({'id': 0, 'name': 'System'}, f"Session {SESSION_PATH} not found.")
        print_red({'id': 0, 'name': 'System'}, "Please enter the Docker instance to generate a session file.")
        print_red({'id': 0, 'name': 'System'}, "Or copy the session file to the container.")
        print_red({'id': 0, 'name': 'System'}, "Run docker exec -it tg-archive /bin/bash")
        print_red({'id': 0, 'name': 'System'}, "cd /session && /usr/local/bin/tg-archive --sync")
        while not os.path.exists(SESSION_PATH):
            time.sleep(10)

if __name__ == '__main__':
    check_session()
    asyncio.get_event_loop().run_until_complete(process_groups())
    run_periodically(3600, lambda: asyncio.get_event_loop().run_until_complete(process_groups()))
