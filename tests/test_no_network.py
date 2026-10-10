"""A standard run opens no network connection.

docs/security-and-deployment.md says a local run sends nothing anywhere. This
runs the command line in a fresh Python process with an audit hook installed
before anything is imported. The hook records and refuses every outbound
connection, DNS lookup and HTTP request, so the run fails if one is attempted,
and the test fails even if the caller swallowed the refusal. The input mixes
years computed by the bundled TAXSIM-35 executable and by PolicyEngine,
including a record with no state tax.

urllib3 binds a socket to the loopback address on import to test for IPv6;
that sends nothing and is allowed.
"""

import os
import subprocess
import sys

import pandas as pd

GUARDED_RUN = r"""
import sys

BLOCKED = {
    "socket.connect", "socket.getaddrinfo",
    "socket.gethostbyname", "socket.gethostbyname_ex", "socket.gethostbyaddr",
    "socket.getnameinfo", "socket.sendto", "socket.sendmsg",
    "urllib.Request", "http.client.connect", "ftplib.connect",
    "smtplib.connect", "imaplib.open", "poplib.connect", "nntplib.connect",
    "telnetlib.Telnet.open", "webbrowser.open",
}
log_path = sys.argv[1]


def guard(event, args):
    if event in BLOCKED:
        with open(log_path, "a") as log:
            log.write(f"{event} {args!r}\n")
        raise RuntimeError(f"network access during a run: {event}")


sys.addaudithook(guard)
sys.argv = ["policyengine-taxsim", "policyengine", sys.argv[2], "-o", sys.argv[3]]
from policyengine_taxsim.cli import cli

cli()
"""

INPUT = """taxsimid,year,state,mstat,page,sage,depx,age1,pwages,swages,intrec,pensions,gssi,rentpaid,proptax,mortgage,idtl
1,2019,5,2,40,38,1,4,60000,25000,300,0,0,0,4000,9000,2
2,2023,33,1,30,0,0,0,52000,0,0,0,0,14000,0,0,2
3,2023,21,2,67,66,0,0,0,0,1200,30000,36000,0,3000,0,2
4,2024,0,1,45,0,1,12,38000,0,0,0,0,9000,0,0,0
"""


def test_command_line_run_opens_no_connection(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text(INPUT)
    output = tmp_path / "output.csv"
    attempts = tmp_path / "network.log"
    attempts.touch()
    environment = dict(os.environ)
    # Empty download caches, so nothing can be satisfied from an earlier run.
    environment["HF_HOME"] = str(tmp_path / "hf")
    environment["XDG_CACHE_HOME"] = str(tmp_path / "cache")
    result = subprocess.run(
        [sys.executable, "-c", GUARDED_RUN, str(attempts), str(source), str(output)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert attempts.read_text() == "", (
        f"network access attempted:\n{attempts.read_text()}"
    )
    assert result.returncode == 0, result.stderr[-3000:]
    results = pd.read_csv(output)
    assert results["taxsimid"].tolist() == [1, 2, 3, 4]
    assert results["fiitax"].notna().all()
