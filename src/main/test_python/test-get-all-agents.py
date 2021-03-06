import logging
import re
from datetime import datetime
# import pymongo

from multiprocessing import Pool, Manager

from jenkins_tools.common import Jenkins
import argparse
from lxml import etree
import pandas as pd

logger = logging.getLogger()
COMMAND_LAUNCHER = "hudson.slaves.CommandLauncher"
SSH_LAUNCHER = "hudson.plugins.sshslaves.SSHLauncher"

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("--url", required=True)
arg_parser.add_argument("--username", required=True)
arg_parser.add_argument("--password", required=True)
args = arg_parser.parse_args()
url = args.url
username = args.username
password = args.password

j = Jenkins(url, username, password)
if j.check_connection():
    logger.info("Success")
else:
    logger.error("Fail")


def get_agents():
    return j.get_agents()


def get_agent_launcher(agent_config: etree.Element):
    launcher = agent_config.find("launcher")
    launcher_class = launcher.attrib['class']
    return launcher_class, launcher


manager = Manager()
agent_candidates = manager.list()
agent_info = manager.list()
agent_info_group_by = manager.dict()


def handle_agent(agent):
    name = agent['displayName']
    config = j.get_agent_config(name)
    launcher_class, launcher = get_agent_launcher(config)
    if launcher_class == SSH_LAUNCHER:
        host = launcher.find("host").text
    elif launcher_class == COMMAND_LAUNCHER:
        agent_command = launcher.find("agentCommand").text
        host = agent_command.split(" ")[-1]
    agent_info.append({"name": name, "host": host, "launcher_class": launcher_class})


if __name__ == "__main__":
    output_file = "~/output.xlsx"
    writer = pd.ExcelWriter(output_file)
    agents = get_agents()
    agent_ci = list(filter(lambda agent: re.compile(f"swfarm-.*").match(agent['displayName']), agents))
    agent_no_ci = list(filter(lambda agent: not re.compile(f"swfarm-.*").match(agent['displayName']), agents))
    with Pool() as pool:
        r = pool.map(handle_agent, agent_ci)
        print(len(agent_info))
        b = []
        for each_agent in agent_info:
            if each_agent['host'] in agent_info_group_by:
                agent_info_group_by[each_agent['host']].append(each_agent)
            else:
                agent_info_group_by[each_agent['host']] = [each_agent]
            b.append([each_agent['name'], each_agent['host'], each_agent['launcher_class']])
        df = pd.DataFrame(b, columns=["name", "host", "launcher_class"])
        df.to_excel(excel_writer=writer)
        writer.close()
        for a in agent_info_group_by:
            print(a, agent_info_group_by[a])
