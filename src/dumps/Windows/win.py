import re
import shlex
import subprocess
from managers.devicemanager import DeviceManager
from .cpuid import CPUID
from error.cpu_err import cpu_err


class WindowsHardwareManager:
    """
    Instance, implementing `DeviceManager`, for extracting system information
    from Windows systems using the `WMI` infrastructure.

    https://docs.microsoft.com/en-us/windows/win32/wmisdk/wmi-start-page
    """

    def __init__(self, parent: DeviceManager):
        self.info = parent.info
        self.pci = parent.pci
        self.intel = parent.intel

    def dump(self):
        self.cpu_info()
        self.gpu_info()
        self.net_info()
        self.audio_info()

    # Credits: https://github.com/flababah/cpuid.py/blob/master/example.py#L25
    def is_set(self, cpu, leaf, subleaf, reg_idx, bit):
        regs = cpu(leaf, subleaf)

        return bool((1 << bit) & regs[reg_idx])

    def cpu_info(self):

        # Credits to https://github.com/flababah
        # for writing this wonderful utility.
        #
        # See: https://github.com/flababah/cpuid.py
        cpu = CPUID()

        # Base command we'll be using to get some basic information using WMI.
        # We define a variable for it as a placehoder.
        #
        # As not to write it all over again
        # for each command we need to use it in.
        cmd = '"Get-WmiObject -Class Win32_Processor | Select-Object -ExpandProperty {}"'
        cmdlet = 'powershell -Command {}'

        try:
            # CPU model
            model = subprocess.check_output(shlex.split(
                cmdlet.format(cmd.format('Name')))).decode().strip()

            # Number of physical cores
            cores = subprocess.check_output(shlex.split(
                cmdlet.format(cmd.format('NumberOfCores')))).decode().strip()

            # Number of logical processors (threads)
            threads = subprocess.check_output(shlex.split(
                cmdlet.format(cmd.format('NumberOfLogicalProcessors')))).decode().strip()
        except Exception as e:
            cpu_err(e)

        else:
            SSE = ['sse', 'sse2', 'sse3', 'sse4.1', 'sse4.2']
            SSE_OP = [
                (1, 0, 3, 25),  # SSE
                (1, 0, 3, 26),  # SSE2
                (1, 0, 2, 0),   # SSE3
                (1, 0, 2, 19),  # SSE4.1
                (1, 0, 2, 20)   # SSE4.2
            ]
            SSSE3 = self.is_set(cpu, 1, 0, 2, 9)

            highest = 'Unknown'

            if SSE:
                for i in range(len(SSE)):
                    if self.is_set(cpu, *SSE_OP[i]):
                        if highest.lower() == 'unknown':
                            highest = SSE[i].upper()

                        elif float(highest[3:] if highest[3:] else 1) < float(SSE[i][3:]):
                            highest = SSE[i].upper()

            self.info['CPU'].append({
                model: {
                    'SSE': highest,
                    'SSSE3': 'Supported' if SSSE3 else 'Not Available',
                    'Cores': cores,
                    'Threads': threads
                }
            })

    def gpu_info(self):
        cmdlet = 'powershell -Command {}'
        cmd = '"Get-WmiObject -Class Win32_VideoController | Select-Object -ExpandProperty {}"'

        try:
            gpus = subprocess.check_output(shlex.split(
                cmdlet.format(cmd.format('Name')))).decode().split('\n')

            pci = subprocess.check_output(shlex.split(
                cmdlet.format(cmd.format('PNPDeviceID')))).decode().split('\n')

        except:
            return
        else:
            for i in range(len(gpus)):
                match = re.search('(VEN_(\d|\w){4})\&(DEV_(\d|\w){4})', pci[i])

                ven, dev = 'Unable to detect.', 'Unable to detect.'

                if match:
                    ven, dev = ['0x' + x.split('_')[1]
                                for x in match.group(0).split('&')]

                    igpu = self.intel.get(dev.upper()[2:], {})

                    if igpu:
                        CPU = self.info['CPU'][0][list(
                            self.info['CPU'][0].keys())[0]]

                        self.info['CPU'][0] = {
                            list(self.info['CPU'][0].keys())[0]: CPU | {
                                'Codename': igpu.get('codename')
                            }
                        }

                if not gpus[i]:
                    continue

                self.info['GPU'].append({
                    gpus[i]: {
                        'Device ID': dev,
                        'Vendor': ven
                    }
                })

    def net_info(self):
        cmdlet = 'powershell -Command {}'
        cmd = '"Get-WmiObject -Class Win32_NetworkAdapter | Select-Object -ExpandProperty {}"'

        try:
            paths = subprocess.check_output(shlex.split(
                cmdlet.format(cmd.format('PNPDeviceID')))).decode().split('\n')
        except:
            return
        else:
            for i in range(len(paths)):
                pci = 'pci' in paths[i].lower()

                if pci:
                    match = re.search(
                        '(VEN_(\d|\w){4})\&(DEV_(\d|\w){4})', paths[i])

                    ven, dev = 'Unable to detect.', 'Unable to detect.'

                    if match:
                        ven, dev = ['0x' + x.split('_')[1]
                                    for x in match.group(0).split('&')]

                    try:
                        model = self.pci.get_item(dev[2:], ven[2:])
                    except:
                        continue

                    if not model:
                        continue

                    self.info['Network'].append({
                        model.get('device'): {
                            'Device ID': dev,
                            'Vendor': ven
                        }
                    })

    def audio_info(self):
        cmdlet = 'powershell -Command {}'
        cmd = '"Get-WmiObject Win32_SoundDevice | Select-Object -ExpandProperty {}"'

        try:
            paths = subprocess.check_output(shlex.split(
                cmdlet.format(cmd.format('PNPDeviceID')))).decode().split('\n')
        except:
            return
        else:
            for i in range(len(paths)):
                is_valid = 'hdaudio' in paths[i].lower()

                if is_valid:
                    match = re.search(
                        '(VEN_(\d|\w){4})\&(DEV_(\d|\w){4})', paths[i])

                    ven, dev = 'Unable to detect.', 'Unable to detect.'

                    if match:
                        ven, dev = ['0x' + x.split('_')[1]
                                    for x in match.group(0).split('&')]

                        try:
                            model = self.pci.get_item(dev[2:], ven[2:])
                        except:
                            continue

                        if not model:
                            continue

                        self.info['Audio'].append({
                            model.get('device'): {
                                'Device ID': dev,
                                'Vendor': ven
                            }
                        })
