"""Lab 7: one OpenFlow 1.3 switch and four hosts."""

from mininet.topo import Topo


class Lab7Topo(Topo):
    def build(self):
        switch = self.addSwitch('s1', protocols='OpenFlow13')
        for number in range(1, 5):
            host = self.addHost(
                'h{}'.format(number),
                ip='10.0.0.{}/24'.format(number),
                mac='00:00:00:00:00:0{}'.format(number),
            )
            self.addLink(host, switch)


topos = {'lab7': Lab7Topo}
