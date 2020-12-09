'''
Usage:

python fix_greenboard_values.py <list of version strings>

Examples:

python fix_greenboard_values.py 7.0.0-3874
python fix_greenboard_values.py 7.0.0
python fix_greenboard_values.py 7.0.0,6.6.1

'''

from couchbase.cluster import Cluster, ClusterOptions
from couchbase.auth import PasswordAuthenticator
import traceback
from couchbase.collection import ReplaceOptions
from couchbase.exceptions import CASMismatchException, DocumentExistsException
import sys
import logging

logger = logging.getLogger("fix_greenboard_values")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

cluster = Cluster("couchbase://172.23.121.84", ClusterOptions(
    PasswordAuthenticator("Administrator", "password")))

server_bucket = cluster.bucket("server")
greenboard_bucket = cluster.bucket("greenboard")
greenboard_collection = greenboard_bucket.default_collection()

args = sys.argv
if len(args) < 2:
    logger.error("please supply versions to fix")
    sys.exit(1)
supplied_versions = args[1].split(",")
versions = set()

for v in supplied_versions:
    for version in list(server_bucket.query("select raw `build` from server where `build` like '%{}%' group by `build`".format(v))):
        versions.add(version)

for version in versions:
    logger.info("fixing {}".format(version))
    try:
        while True:
            doc_id = "{}_server".format(version)

            doc = greenboard_collection.get(doc_id)
            cas = doc.cas
            greenboard = doc.content_as[dict]

            for row in server_bucket.query("select build_id, os, component, name, duration, totalCount, failCount, result from server where `build` = '{}'".format(version)):
                try:
                    all_runs = greenboard["os"][row["os"]][row["component"]][row["name"]]

                    keys_to_check = ["duration", "failCount", "result", "totalCount"]

                    for run in all_runs:
                        if row["build_id"] == run["build_id"]:
                            for key in keys_to_check:
                                if key in row and key in run and row[key] != run[key]:
                                    logger.info("corrected {} from {} to {} for {} in {}".format(key, run[key], row[key], row["name"], version))
                                    run[key] = row[key]

                except Exception:
                    continue

            try:
                greenboard_collection.replace(doc_id, greenboard, ReplaceOptions(cas=cas))
                break
            except (CASMismatchException, DocumentExistsException):
                continue
            except Exception:
                traceback.print_exc()

    except Exception:
        traceback.print_exc()