#!/usr/bin/env python
# coding: utf-8
import argparse
from concurrent.futures import ProcessPoolExecutor
import glob
import os
import urllib3

import pandas as pd
import requests
from ruamel.yaml import YAML

# Path data
CSV = "data/citizen-science-projects-nl.csv"
DATA = "data/categories"
NOT_OK = ":x:"
OK = ":white_check_mark:"

# Ignore InsecureRequestWarning warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Setup YAML
y = YAML()
y.default_flow_style = False
y.explicit_start = True
y.indent(sequence=4, offset=2)


def read_csv_data():
    """Read CSV data and output individual yml files."""
    csv = pd.read_csv(CSV)

    # Find unique categories
    categories = pd.unique(csv["category"])
    categories.sort()

    # Save rows csv to yaml files
    y = YAML()
    y.default_flow_style = False
    y.explicit_start = True
    y.indent(sequence=4, offset=2)

    for cat in range(len(categories)):
        PATH_CATEGORY = os.path.join(DATA, categories[cat])
        if not os.path.exists(PATH_CATEGORY):
            os.makedirs(PATH_CATEGORY)
        cat_data = csv[csv["category"] == categories[cat]].copy()
        # Save each line of each cateogry in json file
        # but only if file was updated
        for i, r in cat_data.iterrows():
            FILE_NAME = r['name'].replace(" ", "_").replace('/', '_')
            PATH_FILE = os.path.join(PATH_CATEGORY, f"{FILE_NAME}.yml")
            dict_r = r.to_dict()
            if os.path.isfile(PATH_FILE):
                with open(PATH_FILE, "r") as old_file:
                    old = y.load(old_file.read())
                    if old is None:
                        save_dict_to_yaml(PATH_FILE, dict_r)
                    #  if not equal then overwrite with new
                    elif not dict(old) == dict(dict_r):
                        old_file.close()
                        save_dict_to_yaml(PATH_FILE, dict_r)
            else:
                save_dict_to_yaml(PATH_FILE, dict_r)


def save_dict_to_yaml(PATH, dict):
    with open(PATH, 'w') as file:
        start_date = dict["start_date"]
        try:
            if isinstance(start_date, int) or isinstance(start_date, float):
                dict["start_date"] = int(start_date)
        except ValueError:
            dict["start_date"] = None
        y.dump(dict, file)


def read_yml_files():
    """Read from yaml files each category and save to df."""
    files = []
    y = YAML()
    y.default_flow_style = None
    y.explicit_start = True
    y.indent(sequence=4, offset=2)

    for filename in glob.iglob(f"{DATA}/**/*", recursive=True):
        if not os.path.isdir(filename):
            with open(filename, "r") as file:
                row = y.load(file.read())
                files.append(row)

    df = pd.DataFrame(files)

    # Check validity of urls
    list_urls = []
    for i, r in df.iterrows():
        list_urls.append({
            "url": r["project_information_url"],
            "name": r["name"]})
    problems_url = pd.DataFrame(check_urls(list_urls), columns=[
        "name", "url", "error"])
    problems_url["icon"] = NOT_OK
    df = df.merge(problems_url, how="left", on="name")

    # Clean df before saving
    df_save = df.copy()
    df_save.drop(columns=["icon", "url", "error"], inplace=True)
    # Save to CSV
    df_save.to_csv("data/citizen-science-projects-nl.csv", index=False)
    # Save to Excel
    df_save.to_excel("data/citizen-science-projects-nl.xlsx",
                     index=False, engine='openpyxl')

    return df


def check_url(url, name):
    try:
        response = requests.head(
            url, allow_redirects=True, verify=False, timeout=25)
        if response.status_code in [301, 302]:
            return name, url, f'Redirects to {response.headers["Location"]}'
    except Exception as e:
        return name, url, repr(e)


def check_urls(url_list):
    with ProcessPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(check_url, **file) for file in url_list]
        responses = [future.result() for future in futures]

    return [r for r in responses if r is not None]


def create_readme(df):
    """Retrieve text from README.md and update it."""
    readme = str

    categories = pd.unique(df["category"])
    categories.sort()

    with open('README.md', 'r', encoding='utf-8') as read_me_file:
        read_me = read_me_file.read()
        splits = read_me.split('<!---->')

        # Initial project description
        text_intro = splits[0]

        # Contribution and contacts
        text_contributing = splits[3]
        text_contacts = splits[4]

        # TOC
        toc = "\n\n- [Awesome Citizen Science Projects](#awesome-citizen-science-projects)\n"
        # Add categories
        for cat in range(len(categories)):
            toc += f"  - [{categories[cat]}](#{categories[cat]})" + "\n"
        # Add contributing and contact to TOC
        toc += "- [Contributing guidelines](#contributing-guidelines)\n"
        toc += "- [Contacts](#contacts)\n"

    # Add first part and toc to README
    readme = text_intro + "<!---->" + toc + "\n<!---->\n"

    # Add projects subtitle
    readme += "\n## Projects\n"

    # Add individual categories to README
    list_blocks = ""
    for cat in range(len(categories)):
        block = f"\n### {categories[cat]}\n\n"
        filtered = df[df["category"] == categories[cat]]
        list_items = ""
        for i, r in filtered.iterrows():
            try:
                start_date = int(r['start_date'])
            except:
                start_date = "NA"
            if not pd.isna(r['icon']):
                project = f"- {r['icon']}  [{r['name']}]({r['project_information_url']}) - {r['description']} (`{start_date}` - `{str(r['end_date'])}`)\n"
                list_items = list_items + project
            else:
                project = f"- [{r['name']}]({r['project_information_url']}) - {r['description']} (`{start_date}` - `{str(r['end_date'])}`)\n"
                list_items = list_items + project
        list_blocks = list_blocks + block + list_items

    # Add to categories to README.md
    readme += list_blocks + "\n"

    # Add contribution and contacts
    readme += '<!---->' + text_contributing
    readme += '<!---->' + text_contacts

    with open('README.md', 'w+', encoding='utf-8') as sorted_file:
        sorted_file.write(readme)


def read_yml_files_to_readme():
    df = read_yml_files()
    create_readme(df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-to-yaml",
                        dest="csv_to_yaml",
                        help="Read the CSV and convert each project to YAML",
                        action="store_true")
    parser.add_argument("--yaml-to-csv-to-readme",
                        dest="yaml_to_csv_to_readme", help="Read all the YAML files and convert them to CSV",
                        action="store_true")
    args = parser.parse_args()

    if args.csv_to_yaml:
        read_csv_data()
    if args.yaml_to_csv_to_readme:
        read_yml_files_to_readme()
