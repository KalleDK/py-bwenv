#!/usr/bin/env python3

import json
import sys
import subprocess
import os
import logging

logger = logging.getLogger()

class BW:
    def __init__(self, key: str, folder_id: str) -> None:
        self._key = key
        self._folder_id = folder_id

    def exec(self, *args, input=None, session=True):
        env = None
        if session:
            env = os.environ.copy()
            env["BW_SESSION"] = self._key
        return subprocess.run(["bw", *args, "--nointeraction"], input=input, text=True, capture_output=True, env=env)
    
    def sync(self):
        self.exec("sync")
        logger.log(logging.INFO, "Synced")

    def get_item(self, name: str):
        res = self.exec("get", "item", name)
        res.check_returncode()
        return json.loads(res.stdout)
    
    def get_values(self, name: str):
        item = self.get_item(name)
        return { field['name']: field['value'] for field in item["fields"] }
    
    def get_uuid(self, name: str):
        item = self.get_item(name)
        return item['id']
    
    def exists(self, name: str):
        try:
            self.get_item(name)
            return True
        except:
            return False
    
    def encode(self, obj):
        line = json.dumps(obj)
        res = self.exec("encode", input=line)
        return res.stdout

    def update_values(self, name: str, values: dict[str, str]):
        item = self.get_item(name)
        item['fields'] = [{"name": key, "value": val, "type": 0} for key, val in values.items()]
        encoded = self.encode(item)
        self.exec("edit", "item", item['id'], input=encoded)

        logger.log(logging.INFO, f"Updated {name}")
    
    def set_values(self, name: str, values: dict[str, str]):
        if self.exists(name):
            return self.update_values(name, values)
        
        item = {
            "secureNote": {
                "type": 0
            },
            "object": "item",
            "folderId": self._folder_id,
            "type": 2,
            "name": name,
            "fields": [{"name": key, "value": val, "type": 0} for key, val in values.items()]
        }

        encoded = self.encode(item)
        res = self.exec("create", "item", input=encoded)

        logger.log(logging.INFO, f"Created {name}")




def set_bw(bw: BW, itemname, filename):
    lines: list[str]
    if filename=="-":
        lines = sys.stdin.readlines()
    else:
        with open(filename, "rt") as fp:
            lines = fp.readlines()
    values = {
        p.split("=", maxsplit=1)[0]: p.split("=", maxsplit=1)[1].strip() for p in lines
    }

    bw.set_values(itemname, values)

def get_bw(bw: BW, itemname, filename):
    values = bw.get_values(itemname)
    lines = [f"{key}={value}\n" for key, value in values.items()]
    if filename == "-":
        sys.stdout.writelines(lines)
    else:
        with open(filename, "wt") as fp:
            fp.writelines(lines)
    logger.log(logging.INFO, f"Loaded {itemname}")


import argparse
parser = argparse.ArgumentParser(description='Bitwarden Environment')
subp = parser.add_subparsers(dest="action")

get_parser = subp.add_parser("get")
get_parser.add_argument('NAME', help='name of item')
get_parser.add_argument('-o', default="-", help='output file -=stdout')
get_parser.add_argument('-s', action='store_true', help='sync')

set_parser = subp.add_parser("set")
set_parser.add_argument('NAME', help='name of item')
set_parser.add_argument('-i', default="-", help='input file -=stdin')
set_parser.add_argument('-s', action='store_true', help="sync")

sync_parser = subp.add_parser("sync")

def main():
    FORMAT = '%(message)s'
    logging.basicConfig(level=logging.INFO, format=FORMAT)

    KEY=os.environ.get("BW_SESSION")
    if KEY is None:
        logger.fatal("No BW_SESSION")
        exit(1)

    config_file = "bwenv.json"
    try:
        with open(config_file, "rt") as fp:
            config = json.load(fp)
    except:
        logger.fatal(f"Missing config_file {config_file}")
        exit(1)
    

    bw = BW(KEY, config["folder_id"])

    args = parser.parse_args()
    if args.action == "set":
        set_bw(bw, args.NAME, args.i)
        if args.s:
            bw.sync()
    elif args.action == "get":
        if args.s:
            bw.sync()
        get_bw(bw, args.NAME, args.o)
    elif args.action == "sync":
        bw.sync()
    else:
        print("Nothing to do", file=sys.stderr)

if __name__ == "__main__":
    main()