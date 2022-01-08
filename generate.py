import glob
import io
import json
import os
import shutil
import zipfile
from typing import List

import pydantic
import requests
from dateutil import parser
from pydantic import BaseModel

GITHUB_TOKEN = os.getenv("REPO_ACCESS_TOKEN")


class PluginDef(BaseModel):
    user: str
    repo: str
    branch: str


class ManifestBuilder:
    def __init__(self):
        self.manifests = []

    def run(self):
        plugins = pydantic.parse_file_as(List[PluginDef], "plugins.json")
        self.delete_old_plugin_folder()
        for plugin in plugins:
            self.process_plugin(plugin)
        self.write_manifest()

    @staticmethod
    def delete_old_plugin_folder():
        try:
            shutil.rmtree("plugins")
        except FileNotFoundError:
            pass

    def process_plugin(self, plugin: PluginDef):
        print(f" ==== {plugin.user}/{plugin.repo} ==== ")
        # get latest release artifact
        repo_artifacts = requests.get(
            f"https://api.github.com/repos/{plugin.user}/{plugin.repo}/actions/artifacts",
            auth=(plugin.user, GITHUB_TOKEN)
        )
        repo_artifacts.raise_for_status()
        release_artifact = sorted(
            (artifact for artifact in repo_artifacts.json()['artifacts'] if artifact['name'] == 'ReleaseArtifact'),
            key=lambda artifact: artifact['updated_at'],
            reverse=True
        )[0]
        print(f"Found artifact: {release_artifact['name']}")
        print(f"ID: {release_artifact['id']}")
        print(f"Size: {release_artifact['size_in_bytes']}B")
        print(f"Updated at: {release_artifact['updated_at']}")
        artifact_download_url = release_artifact['archive_download_url']

        # download artifact
        release_zip_req = requests.get(artifact_download_url, auth=(plugin.user, GITHUB_TOKEN))
        release_zip_req.raise_for_status()
        release_zip_data = io.BytesIO(release_zip_req.content)
        release_zip = zipfile.ZipFile(release_zip_data)

        # create directory and unzip artifact
        os.makedirs(f"plugins/{plugin.repo}", exist_ok=True)
        release_zip.extractall(f"plugins/{plugin.repo}")

        # grab the manifest from the json in the created directory
        plugin_json = glob.glob(f"plugins/{plugin.repo}/*.json")[0]
        plugin_zip = glob.glob(f"plugins/{plugin.repo}/*.zip")[0]
        print(f"JSON: {plugin_json}")
        print(f"Zip: {plugin_zip}")

        # grab plugin manifest and update
        with open(plugin_json) as f:
            manifest = json.load(f)

        manifest.update({
            "IsHide": False,
            "IsTestingExclusive": False,
            "LastUpdated": int(parser.parse(release_artifact['updated_at']).timestamp()),
            "DownloadLinkInstall": f"https://raw.githubusercontent.com/zhudotexe/FFXIV_DalamudPlugins/main/{plugin_zip}",
            "DownloadLinkTesting": f"https://raw.githubusercontent.com/zhudotexe/FFXIV_DalamudPlugins/main/{plugin_zip}",
            "DownloadLinkUpdate": f"https://raw.githubusercontent.com/zhudotexe/FFXIV_DalamudPlugins/main/{plugin_zip}"
        })
        self.manifests.append(manifest)
        print()

    def write_manifest(self):
        with open("manifest.json", "w") as f:
            json.dump(self.manifests, f, indent=2)


if __name__ == '__main__':
    ManifestBuilder().run()
