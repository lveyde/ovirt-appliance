#!/usr/bin/env python
# vim: et ts=4 sw=4 sts=4

import logging
from logging import debug, info

logging.basicConfig(level=logging.DEBUG)

import unittest
import sh
from virt import Image, VM, CloudConfig


class MachineTestCase(unittest.TestCase):
    @staticmethod
    def _start_vm(name, srcimg, tmpimg, ssh_port, ipsuffix):
        debug("Strating new VM %s" % name)
        img = Image(srcimg).reflink(tmpimg)
        dom = VM.create(name, img, ssh_port=ssh_port)

        cc = CloudConfig()
        cc.instanceid = name + "-ci"
        cc.password = name
        cc.runcmd = "ip addr add 10.0.2.%s/24 dev eth0" % ipsuffix
        dom.set_cloud_config(cc)

        return dom


class NodeTestCase(MachineTestCase):
    @classmethod
    def setUpClass(cls):
        debug("SetUpClass %s" % cls)
        cls.node = cls._start_vm("node-%s" % cls.__name__,
                                 "ovirt-node-appliance.qcow2",
                                 "node-test.qcow2", 7001, 77)

    @classmethod
    def tearDownClass(cls):
        debug("Tearing down %s" % cls)
        cls.node.undefine()

    def setUp(self):
        debug("Setting up %s" % self)
        self.snapshot = self.node.snapshot()
        self.node.start()

    def tearDown(self):
        debug("Tearing down %s" % self)
        self.snapshot.revert()


class IntegrationTestCase(MachineTestCase):
    @classmethod
    def setUpClass(cls):
        print("SetUpClass %s" % cls)
        cls.node = cls._start_vm("node", "ovirt-node-appliance.qcow2",
                                 "node-test.qcow2", 420077, 77)
        cls.engine = cls._start_vm("engine", "ovirt-engine-appliance.qcow2",
                                   "engine-test.qcow2", 420088, 88)

    @classmethod
    def tearDownClass(cls):
        info("Tearing down %s" % cls)
        cls.node = None
        cls.engine = None

    def setUp(self):
        self.node_snapshot = self.node.snapshot()
        self.node.start()

        self.engine_snapshot = self.engine.snapshot()
        self.engine.start()

    def tearDown(self):
        self.node_snapshot.revert()
        self.engine_snapshot.revert()


class TestNodeTestcase(NodeTestCase):
    """Let's ensure that the basic functionality is working
    """
    def test_snapshots_work(self):
        has_kernel = lambda: "kernel" in self.node.ssh("rpm -q kernel")

        self.assertTrue(has_kernel())

        with self.node.snapshot().context():
            self.node.ssh("rpm -e --nodeps kernel")
            with self.assertRaises(sh.ErrorReturnCode_1):
                has_kernel()

        self.assertTrue(has_kernel())

    def test_ssh_works(self):
        self.node.ssh("pwd")

    def test_reboot_works(self):
        with self.assertRaises(sh.ErrorReturnCode_255):
            self.node.ssh("reboot")
        self.node.wait_reboot(timeout=60)
        self.node.ssh("pwd")


class TestBasicNode(NodeTestCase):
    def test_required_packages(self):
        pkgs = ["kernel", "vdsm"]
        self.node.ssh("rpm -q " + " ".join(pkgs))


@unittest.skip("We need to test the installed image to fix this")
class TestImgbaseNode(NodeTestCase):
    def test_installed(self):
        debug("%s" % self.node.ssh("imgbase --version"))

    def test_has_vgs(self):
        vgs = self.node.ssh("vgs --noheadings").strip().splitlines()
        debug("VGs: %s" % vgs)
        self.assertGreater(len(vgs), 0, "No VGs found")

    def test_has_layout(self):
        self.node.ssh("imgbase layout")


if __name__ == "__main__":
    unittest.main()