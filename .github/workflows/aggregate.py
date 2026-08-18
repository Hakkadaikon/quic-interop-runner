import argparse
import json
import sys


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s", "--server", help="server implementations (comma-separated)"
    )
    parser.add_argument(
        "-c", "--client", help="client implementations (comma-separated)"
    )
    parser.add_argument("-t", "--start-time", help="start time")
    parser.add_argument("-l", "--log-dir", help="log directory")
    parser.add_argument("-o", "--output", help="output file (stdout if not set)")
    parser.add_argument(
        "-m",
        "--merge-with",
        help="prior aggregated result.json to fill in server/client pairs "
        "not covered by this run (e.g. a partial re-run limited to one server)",
    )
    return parser.parse_args()


args = get_args()
run_servers = args.server.split(",")
clients = args.client.split(",")

prior = None
if args.merge_with:
    try:
        with open(args.merge_with) as f:
            prior = json.load(f)
    except IOError:
        print("Warning: Couldn't open merge-with file " + args.merge_with)

# The full server list is this run's servers plus any extra servers already
# present in the prior result (so a partial run doesn't drop them).
servers = list(run_servers)
if prior:
    for server in prior.get("servers", []):
        if server not in servers:
            servers.append(server)

result = {
    "servers": servers,
    "clients": clients,
    "log_dir": get_args().log_dir,
    "start_time": int(get_args().start_time),
    "results": [],
    "measurements": [],
    "tests": dict(prior["tests"]) if prior else {},
    "urls": dict(prior["urls"]) if prior else {},
}
if prior:
    if "end_time" in prior:
        result["end_time"] = prior["end_time"]
    if "quic_version" in prior:
        result["quic_version"] = prior["quic_version"]


def prior_entry(server: str, client: str, cat: str):
    if not prior:
        return None
    try:
        client_idx = prior["clients"].index(client)
        server_idx = prior["servers"].index(server)
    except ValueError:
        return None
    idx = client_idx * len(prior["servers"]) + server_idx
    entries = prior.get(cat, [])
    return entries[idx] if idx < len(entries) else None


def parse(server: str, client: str, cat: str):
    if server not in run_servers:
        entry = prior_entry(server, client, cat)
        result[cat].append(entry if entry is not None else [])
        return
    filename = server + "_" + client + "_" + cat + ".json"
    try:
        with open(filename) as f:
            data = json.load(f)
    except IOError:
        print("Warning: Couldn't open file " + filename)
        entry = prior_entry(server, client, cat)
        result[cat].append(entry if entry is not None else [])
        return
    parse_data(server, client, cat, data)


def parse_data(server: str, client: str, cat: str, data: object):
    if len(data["servers"]) != 1:
        sys.exit("expected exactly one server")
    if data["servers"][0] != server:
        sys.exit("inconsistent server")
    if len(data["clients"]) != 1:
        sys.exit("expected exactly one client")
    if data["clients"][0] != client:
        sys.exit("inconsistent client")
    if "end_time" not in result or data["end_time"] > result["end_time"]:
        result["end_time"] = data["end_time"]
    result[cat].append(data[cat][0])
    result["quic_version"] = data["quic_version"]
    result["urls"].update(data["urls"])
    result["tests"].update(data["tests"])


for client in clients:
    for server in servers:
        parse(server, client, "results")
        parse(server, client, "measurements")

if get_args().output:
    f = open(get_args().output, "w")
    json.dump(result, f)
    f.close()
else:
    print(json.dumps(result))
