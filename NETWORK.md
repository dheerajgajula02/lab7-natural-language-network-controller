# Lab 7 running network

Verified on 12 October 2026.

- Mininet VM: `100.73.87.23` over Tailscale, account `mininet`; internal LAN `10.224.76.126`.
- Controller VM: `100.110.3.67` over Tailscale, account `sdn`; internal LAN `10.224.78.132`.
- Ryu 4.27 is running as `sdn`, with `simple_switch_13` and `ofctl_rest`. OpenFlow listens on 6633 and REST on 8080. The PID and log are `/home/sdn/lab7/ryu.pid` and `/home/sdn/lab7/ryu.log`.
- Mininet is running in the root-owned tmux session `lab7-mininet`. It has s1, h1–h4, OpenFlow 1.3, addresses 10.0.0.1–10.0.0.4/24, and sequential MAC addresses ending 01–04.
- `pingall` returned `0% dropped (12/12 received)`. OVS reports `is_connected: true`, bridge protocols `["OpenFlow13"]`, and Ryu REST returns `[1]`.

## Reconnect

```bash
ssh mininet@100.73.87.23
sudo tmux attach -t lab7-mininet
```

Detach with Ctrl+B, then D to leave the network running. Entering `exit` in the Mininet CLI tears down the topology.

Controller access:

```bash
tailscale ssh sdn@sdn-controllers
tail -f ~/lab7/ryu.log
```

## Startup commands used

On the controller:

```bash
ryu-manager --ofp-tcp-listen-port 6633 ryu.app.simple_switch_13 ryu.app.ofctl_rest
```

On Mininet, using `/home/mininet/lab7/topo_lab7.py`:

```bash
sudo mn --custom /home/mininet/lab7/topo_lab7.py --topo lab7 --controller remote,ip=10.224.78.132,port=6633 --switch ovsk,protocols=OpenFlow13 --mac
```

The prior inactive Lab 6 bridges s1/s2 and their veth links were replaced after saving OVS configuration and flows under `/home/mininet/lab7/before_*.txt`. Other VM interfaces were retained.

The controller and Mininet are running persistently for this session; automatic startup after reboot is not configured. The report uses actual xterm window screenshots showing VM output over SSH (`topology_terminal.png` and `controller_terminal.png`). The initial browser evidence-view images were replaced at the user's request. Raw transcripts are retained alongside the screenshots. Temporary screenshot terminals were closed; the detached Mininet session and Ryu remain running.
