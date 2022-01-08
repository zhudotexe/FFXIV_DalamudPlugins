import glob
import io
import json
import os
import time
import zipfile
from typing import List

import pydantic
import requests
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
        for plugin in plugins:
            self.process_plugin(plugin)

    def process_plugin(self, plugin: PluginDef):
        # get latest release artifact
        repo_artifacts = requests.get(
            f"https://api.github.com/repos/{plugin.user}/{plugin.repo}/actions/artifacts",
            auth=(plugin.user, GITHUB_TOKEN)
        )
        repo_artifacts.raise_for_status()
        release_artifact = next(sorted(
            (artifact for artifact in repo_artifacts.json() if artifact['name'] == 'ReleaseArtifact'),
            key=lambda artifact: artifact['updated_at'],
            reverse=True
        ))
        artifact_download_url = release_artifact['archive_download_url']

        # download artifact
        release_zip_req = requests.get(artifact_download_url, auth=(plugin.user, GITHUB_TOKEN))
        release_zip_req.raise_for_status()
        release_zip_data = io.BytesIO(release_zip_req.content)
        release_zip = zipfile.ZipFile(release_zip_data)

        # create directory and unzip artifact
        os.makedirs(plugin.repo, exist_ok=True)
        release_zip.extractall(plugin.repo)

        # grab the manifest from the json in the created directory
        plugin_json = glob.glob(f"{plugin.repo}/*.json")[0]
        plugin_zip = glob.glob(f"{plugin.repo}/*.zip")[0]

        # grab plugin manifest and update
        with open(plugin_json) as f:
            manifest = json.load(f)

        manifest.update({
            "IsHide": False,
            "IsTestingExclusive": False,
            "LastUpdated": int(time.time()),
            "DownloadLinkInstall": f"https://raw.githubusercontent.com/zhudotexe/FFXIV_DalamudPlugins/main/{plugin_zip}",
            "DownloadLinkTesting": f"https://raw.githubusercontent.com/zhudotexe/FFXIV_DalamudPlugins/main/{plugin_zip}",
            "DownloadLinkUpdate": f"https://raw.githubusercontent.com/zhudotexe/FFXIV_DalamudPlugins/main/{plugin_zip}"
        })
        self.manifests.append(manifest)

    def write_manifest(self):
        with open("manifest.json", "w") as f:
            json.dump(self.manifests, f, indent=2)


if __name__ == '__main__':
    ManifestBuilder().run()
