"""USBReader over the hidapi transport (macOS), with a fake `hid` module."""

import time

import pytest

from device import usb_reader
from device.usb_reader import CMD_INIT_1, CMD_INIT_2, CMD_KEEPALIVE, USBReader
from tests.test_usb_decode import SAMPLES, build_packet


class FakeHIDDevice:
    """A meter that starts streaming `stream` once it receives INIT_1.

    `packets` holds reports already queued, e.g. stale data from an earlier session.
    """

    def __init__(self, stream=(), stale=()):
        self.stream = list(stream)
        self.packets = list(stale)
        self.written = []
        self.opened = None
        self.closed = False

    def open(self, vid, pid):
        self.opened = (vid, pid)

    def write(self, data):
        self.written.append(bytes(data))
        if bytes(data[1:]) == CMD_INIT_1:
            self.packets += self.stream
            self.stream = []
        return len(data)

    def read(self, max_length, timeout_ms=0):
        if self.packets:
            return list(self.packets.pop(0))
        time.sleep(0.001)  # timeout: no report
        return []

    def close(self):
        self.closed = True

    def get_manufacturer_string(self):
        return 'FNIRSI'

    def get_product_string(self):
        return 'FNB-58'

    def get_serial_number_string(self):
        return '0CFF01F93C64'


class FakeHID:
    def __init__(self, present, device):
        self.present = present
        self._device = device

    def enumerate(self, vid, pid):
        return [{'vendor_id': vid, 'product_id': pid}] if (vid, pid) in self.present else []

    def device(self):
        return self._device


STALE = build_packet([(1.0, 0.0, 0.0, 0.0, 20.0)])


@pytest.fixture()
def fake_hid(monkeypatch):
    dev = FakeHIDDevice(stream=[build_packet(SAMPLES)], stale=[STALE])
    monkeypatch.setattr(usb_reader, 'USE_HID', True)
    monkeypatch.setattr(usb_reader, 'hid', FakeHID({(0x2E3C, 0x5558)}, dev))
    return dev


def test_hid_session_handshake_readings_and_disconnect(fake_hid):
    reader = USBReader()
    reader.connect()
    assert fake_hid.opened == (0x2E3C, 0x5558)
    assert reader.get_device_info()['serial'] == '0CFF01F93C64'

    got = []
    reader.start_reading(callback=got.append)
    deadline = time.monotonic() + 2
    while len(got) < 4 and time.monotonic() < deadline:
        time.sleep(0.01)
    reader.disconnect()

    # FNB58 session: report ID 0 + INIT_1, INIT_2, INIT_2, then only keep-alives
    sent = [w[1:] for w in fake_hid.written]
    assert all(w[0] == 0 for w in fake_hid.written)
    assert sent[:3] == [CMD_INIT_1, CMD_INIT_2, CMD_INIT_2]
    assert set(sent[3:]) <= {CMD_KEEPALIVE}
    # Stale report from an earlier session was discarded, not reported
    assert [r['voltage'] for r in got] == pytest.approx([s[0] for s in SAMPLES], abs=1e-5)
    assert fake_hid.closed
    assert reader.get_device_info() is None


def test_stop_drains_unread_reports(fake_hid):
    # Reports left unread fill the meter's FIFO and freeze it until replugged.
    fake_hid.stream += [build_packet(SAMPLES)] * 5
    reader = USBReader()
    reader.connect()
    reader.start_reading(callback=lambda r: None)
    reader.disconnect()
    assert fake_hid.packets == []
    assert fake_hid.closed


def test_hid_no_device(monkeypatch):
    monkeypatch.setattr(usb_reader, 'USE_HID', True)
    monkeypatch.setattr(usb_reader, 'hid', FakeHID(set(), FakeHIDDevice()))
    with pytest.raises(ConnectionError, match='No FNIRSI device'):
        USBReader().connect()


def test_hid_missing_package_is_explained(monkeypatch):
    monkeypatch.setattr(usb_reader, 'USE_HID', True)
    monkeypatch.setattr(usb_reader, 'hid', None)
    with pytest.raises(ConnectionError, match='hidapi'):
        USBReader().connect()
