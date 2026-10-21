using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace UsbPortDump
{
    public class UsbPort
    {
        public int Index { get; set; }
        public int Status { get; set; }
        public int Speed { get; set; }
        public bool IsHub { get; set; }
        public int Protocols { get; set; }
        public int V2Flags { get; set; }
        public int PortProperties { get; set; }
        public int CompanionPort { get; set; }
        public string CompanionHub { get; set; }
        public string DeviceName { get; set; }
        public string DeviceId { get; set; }
        public int Vid { get; set; }
        public int Pid { get; set; }
        public List<string> Children { get; set; }
    }

    public class UsbController
    {
        public string Name { get; set; }
        public string InstanceId { get; set; }
        public string[] CompatibleIds { get; set; }
        public string Service { get; set; }
        public string AcpiPath { get; set; }
        public int BusNumber { get; set; }
        public int Address { get; set; }
        public string HubName { get; set; }
        public int PortCount { get; set; }
        public string Error { get; set; }
        public List<UsbPort> Ports { get; set; }
    }

    class DeviceNode
    {
        public string InstanceId;
        public string Name;
    }

    public static class UsbEnum
    {
        const int DIGCF_PRESENT = 0x2;
        const int DIGCF_ALLCLASSES = 0x4;
        const int DIGCF_DEVICEINTERFACE = 0x10;
        const int SPDRP_DEVICEDESC = 0x0;
        const int SPDRP_COMPATIBLEIDS = 0x2;
        const int SPDRP_SERVICE = 0x4;
        const int SPDRP_DRIVER = 0x9;
        const int SPDRP_FRIENDLYNAME = 0xC;
        const int SPDRP_BUSNUMBER = 0x15;
        const int SPDRP_ADDRESS = 0x1C;
        const uint GENERIC_WRITE = 0x40000000;
        const uint FILE_SHARE_WRITE = 0x2;
        const uint OPEN_EXISTING = 3;
        const uint IOCTL_USB_GET_ROOT_HUB_NAME = 0x220408;
        const uint IOCTL_USB_GET_NODE_INFORMATION = 0x220408;
        const uint IOCTL_USB_GET_NODE_CONNECTION_NAME = 0x220414;
        const uint IOCTL_USB_GET_NODE_CONNECTION_DRIVERKEY_NAME = 0x220420;
        const uint IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX = 0x220448;
        const uint IOCTL_USB_GET_HUB_INFORMATION_EX = 0x220454;
        const uint IOCTL_USB_GET_PORT_CONNECTOR_PROPERTIES = 0x220458;
        const uint IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX_V2 = 0x22045C;
        const int MaxHubDepth = 6;

        static readonly Guid HostControllerInterface = new Guid("3abf6f2d-71c4-462a-8a92-1e6861e6af27");
        static readonly Guid DevicePropertyGuid = new Guid("540b947e-8b40-45bc-a8a2-6a0b894cbda2");

        [StructLayout(LayoutKind.Sequential)]
        struct SP_DEVINFO_DATA
        {
            public int cbSize;
            public Guid ClassGuid;
            public int DevInst;
            public IntPtr Reserved;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct SP_DEVICE_INTERFACE_DATA
        {
            public int cbSize;
            public Guid InterfaceClassGuid;
            public int Flags;
            public IntPtr Reserved;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct DEVPROPKEY
        {
            public Guid fmtid;
            public int pid;
        }

        [DllImport("setupapi.dll", EntryPoint = "SetupDiGetClassDevsW", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern IntPtr SetupDiGetClassDevs(ref Guid classGuid, string enumerator, IntPtr hwndParent, int flags);

        [DllImport("setupapi.dll", EntryPoint = "SetupDiGetClassDevsW", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern IntPtr SetupDiGetClassDevsAll(IntPtr classGuid, string enumerator, IntPtr hwndParent, int flags);

        [DllImport("setupapi.dll", SetLastError = true)]
        static extern bool SetupDiEnumDeviceInterfaces(IntPtr deviceInfoSet, IntPtr deviceInfoData, ref Guid interfaceClassGuid, int memberIndex, ref SP_DEVICE_INTERFACE_DATA deviceInterfaceData);

        [DllImport("setupapi.dll", EntryPoint = "SetupDiGetDeviceInterfaceDetailW", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr deviceInfoSet, ref SP_DEVICE_INTERFACE_DATA deviceInterfaceData, IntPtr detail, int detailSize, out int requiredSize, ref SP_DEVINFO_DATA deviceInfoData);

        [DllImport("setupapi.dll", SetLastError = true)]
        static extern bool SetupDiEnumDeviceInfo(IntPtr deviceInfoSet, int memberIndex, ref SP_DEVINFO_DATA deviceInfoData);

        [DllImport("setupapi.dll", EntryPoint = "SetupDiGetDeviceRegistryPropertyW", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool SetupDiGetDeviceRegistryProperty(IntPtr deviceInfoSet, ref SP_DEVINFO_DATA deviceInfoData, int property, out int regType, byte[] buffer, int bufferSize, out int requiredSize);

        [DllImport("setupapi.dll", EntryPoint = "SetupDiGetDevicePropertyW", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool SetupDiGetDeviceProperty(IntPtr deviceInfoSet, ref SP_DEVINFO_DATA deviceInfoData, ref DEVPROPKEY propertyKey, out int propertyType, byte[] buffer, int bufferSize, out int requiredSize, int flags);

        [DllImport("setupapi.dll", EntryPoint = "SetupDiGetDeviceInstanceIdW", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool SetupDiGetDeviceInstanceId(IntPtr deviceInfoSet, ref SP_DEVINFO_DATA deviceInfoData, StringBuilder deviceInstanceId, int deviceInstanceIdSize, out int requiredSize);

        [DllImport("setupapi.dll", SetLastError = true)]
        static extern bool SetupDiDestroyDeviceInfoList(IntPtr deviceInfoSet);

        [DllImport("kernel32.dll", EntryPoint = "CreateFileW", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern SafeFileHandle CreateFile(string fileName, uint desiredAccess, uint shareMode, IntPtr securityAttributes, uint creationDisposition, uint flagsAndAttributes, IntPtr templateFile);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool DeviceIoControl(SafeFileHandle device, uint ioControlCode, byte[] inBuffer, int inBufferSize, byte[] outBuffer, int outBufferSize, out int bytesReturned, IntPtr overlapped);

        static string RegistryString(IntPtr set, ref SP_DEVINFO_DATA data, int property)
        {
            byte[] buffer = new byte[2048];
            int regType;
            int required;
            if (!SetupDiGetDeviceRegistryProperty(set, ref data, property, out regType, buffer, buffer.Length, out required))
            {
                return null;
            }
            return Encoding.Unicode.GetString(buffer, 0, Math.Max(0, required)).TrimEnd('\0');
        }

        static string[] RegistryMultiString(IntPtr set, ref SP_DEVINFO_DATA data, int property)
        {
            string value = RegistryString(set, ref data, property);
            if (value == null)
            {
                return new string[0];
            }
            return value.Split(new char[] { '\0' }, StringSplitOptions.RemoveEmptyEntries);
        }

        static int RegistryInt(IntPtr set, ref SP_DEVINFO_DATA data, int property)
        {
            byte[] buffer = new byte[4];
            int regType;
            int required;
            if (!SetupDiGetDeviceRegistryProperty(set, ref data, property, out regType, buffer, buffer.Length, out required) || required < 4)
            {
                return -1;
            }
            return BitConverter.ToInt32(buffer, 0);
        }

        static string PropertyString(IntPtr set, ref SP_DEVINFO_DATA data, int pid)
        {
            DEVPROPKEY key = new DEVPROPKEY();
            key.fmtid = DevicePropertyGuid;
            key.pid = pid;
            byte[] buffer = new byte[2048];
            int propertyType;
            int required;
            if (!SetupDiGetDeviceProperty(set, ref data, ref key, out propertyType, buffer, buffer.Length, out required, 0))
            {
                return null;
            }
            return Encoding.Unicode.GetString(buffer, 0, Math.Max(0, required)).TrimEnd('\0');
        }

        static string InstanceId(IntPtr set, ref SP_DEVINFO_DATA data)
        {
            StringBuilder builder = new StringBuilder(1024);
            int required;
            if (!SetupDiGetDeviceInstanceId(set, ref data, builder, builder.Capacity, out required))
            {
                return null;
            }
            return builder.ToString();
        }

        static string DisplayName(IntPtr set, ref SP_DEVINFO_DATA data, bool preferBusName)
        {
            string name = null;
            if (preferBusName)
            {
                name = PropertyString(set, ref data, 4);
            }
            if (String.IsNullOrEmpty(name))
            {
                name = RegistryString(set, ref data, SPDRP_FRIENDLYNAME);
            }
            if (String.IsNullOrEmpty(name))
            {
                name = RegistryString(set, ref data, SPDRP_DEVICEDESC);
            }
            return name;
        }

        static Dictionary<string, DeviceNode> DevicesByDriverKey()
        {
            Dictionary<string, DeviceNode> result = new Dictionary<string, DeviceNode>(StringComparer.OrdinalIgnoreCase);
            IntPtr set = SetupDiGetClassDevsAll(IntPtr.Zero, null, IntPtr.Zero, DIGCF_PRESENT | DIGCF_ALLCLASSES);
            if (set == IntPtr.Zero || set == new IntPtr(-1))
            {
                return result;
            }
            try
            {
                for (int index = 0; ; index++)
                {
                    SP_DEVINFO_DATA data = new SP_DEVINFO_DATA();
                    data.cbSize = Marshal.SizeOf(typeof(SP_DEVINFO_DATA));
                    if (!SetupDiEnumDeviceInfo(set, index, ref data))
                    {
                        break;
                    }
                    string driverKey = RegistryString(set, ref data, SPDRP_DRIVER);
                    if (String.IsNullOrEmpty(driverKey) || result.ContainsKey(driverKey))
                    {
                        continue;
                    }
                    DeviceNode node = new DeviceNode();
                    node.InstanceId = InstanceId(set, ref data);
                    node.Name = DisplayName(set, ref data, true);
                    result[driverKey] = node;
                }
            }
            finally
            {
                SetupDiDestroyDeviceInfoList(set);
            }
            return result;
        }

        static SafeFileHandle OpenDevice(string path)
        {
            return CreateFile(path, GENERIC_WRITE, FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
        }

        static string NameIoctl(SafeFileHandle handle, uint code, int connectionIndex, int headerSize)
        {
            byte[] input = new byte[headerSize];
            if (headerSize >= 8)
            {
                BitConverter.GetBytes(connectionIndex).CopyTo(input, 0);
            }
            byte[] output = new byte[4096];
            int returned;
            if (!DeviceIoControl(handle, code, input, input.Length, output, output.Length, out returned, IntPtr.Zero))
            {
                return null;
            }
            int lengthOffset = headerSize >= 8 ? 4 : 0;
            int actual = BitConverter.ToInt32(output, lengthOffset);
            int available = Math.Min(Math.Max(actual, returned), output.Length) - headerSize;
            if (available <= 0)
            {
                return null;
            }
            return Encoding.Unicode.GetString(output, headerSize, available).TrimEnd('\0');
        }

        static int HubPortCount(SafeFileHandle hub)
        {
            int count = 0;
            byte[] node = new byte[256];
            int returned;
            if (DeviceIoControl(hub, IOCTL_USB_GET_NODE_INFORMATION, node, node.Length, node, node.Length, out returned, IntPtr.Zero) && returned > 6)
            {
                count = node[6];
            }
            byte[] extended = new byte[512];
            if (DeviceIoControl(hub, IOCTL_USB_GET_HUB_INFORMATION_EX, extended, extended.Length, extended, extended.Length, out returned, IntPtr.Zero) && returned >= 6)
            {
                count = Math.Max(count, BitConverter.ToUInt16(extended, 4));
            }
            return count;
        }

        static UsbPort ReadPort(SafeFileHandle hub, int index, Dictionary<string, DeviceNode> devices, int depth)
        {
            UsbPort port = new UsbPort();
            port.Index = index;
            port.Status = -1;
            port.Speed = -1;
            port.Protocols = -1;
            port.V2Flags = 0;
            port.PortProperties = -1;
            port.CompanionHub = "";
            port.Children = new List<string>();
            int returned;

            byte[] info = new byte[512];
            BitConverter.GetBytes(index).CopyTo(info, 0);
            if (DeviceIoControl(hub, IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX, info, info.Length, info, info.Length, out returned, IntPtr.Zero) && returned >= 35)
            {
                port.Vid = BitConverter.ToUInt16(info, 12);
                port.Pid = BitConverter.ToUInt16(info, 14);
                port.Speed = info[23];
                port.IsHub = info[24] != 0;
                port.Status = BitConverter.ToInt32(info, 31);
            }

            byte[] v2 = new byte[16];
            BitConverter.GetBytes(index).CopyTo(v2, 0);
            BitConverter.GetBytes(16).CopyTo(v2, 4);
            BitConverter.GetBytes(7).CopyTo(v2, 8);
            if (DeviceIoControl(hub, IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX_V2, v2, v2.Length, v2, v2.Length, out returned, IntPtr.Zero) && returned >= 16)
            {
                port.Protocols = BitConverter.ToInt32(v2, 8);
                port.V2Flags = BitConverter.ToInt32(v2, 12);
            }

            byte[] connector = new byte[1024];
            BitConverter.GetBytes(index).CopyTo(connector, 0);
            if (DeviceIoControl(hub, IOCTL_USB_GET_PORT_CONNECTOR_PROPERTIES, connector, connector.Length, connector, connector.Length, out returned, IntPtr.Zero) && returned >= 16)
            {
                port.PortProperties = BitConverter.ToInt32(connector, 8);
                port.CompanionPort = BitConverter.ToUInt16(connector, 14);
                int actual = Math.Min(BitConverter.ToInt32(connector, 4), returned);
                if (actual > 16)
                {
                    port.CompanionHub = Encoding.Unicode.GetString(connector, 16, actual - 16).TrimEnd('\0');
                }
            }

            if (port.Status == 1)
            {
                string driverKey = NameIoctl(hub, IOCTL_USB_GET_NODE_CONNECTION_DRIVERKEY_NAME, index, 8);
                DeviceNode node;
                if (driverKey != null && devices.TryGetValue(driverKey, out node))
                {
                    port.DeviceName = node.Name;
                    port.DeviceId = node.InstanceId;
                }
                if (port.IsHub && depth < MaxHubDepth)
                {
                    string childHub = NameIoctl(hub, IOCTL_USB_GET_NODE_CONNECTION_NAME, index, 8);
                    if (!String.IsNullOrEmpty(childHub))
                    {
                        CollectChildren(@"\\.\" + childHub, devices, depth + 1, port.Children);
                    }
                }
            }
            return port;
        }

        static void CollectChildren(string hubPath, Dictionary<string, DeviceNode> devices, int depth, List<string> names)
        {
            using (SafeFileHandle hub = OpenDevice(hubPath))
            {
                if (hub.IsInvalid)
                {
                    return;
                }
                int count = HubPortCount(hub);
                for (int index = 1; index <= count; index++)
                {
                    UsbPort child = ReadPort(hub, index, devices, depth);
                    if (child.Status != 1)
                    {
                        continue;
                    }
                    if (!child.IsHub)
                    {
                        names.Add(child.DeviceName ?? String.Format("USB device {0:X4}:{1:X4}", child.Vid, child.Pid));
                    }
                    names.AddRange(child.Children);
                }
            }
        }

        static string InterfacePath(IntPtr set, ref SP_DEVICE_INTERFACE_DATA iface, ref SP_DEVINFO_DATA data)
        {
            int required;
            SetupDiGetDeviceInterfaceDetail(set, ref iface, IntPtr.Zero, 0, out required, ref data);
            if (required <= 0)
            {
                return null;
            }
            IntPtr detail = Marshal.AllocHGlobal(required);
            try
            {
                Marshal.WriteInt32(detail, IntPtr.Size == 8 ? 8 : 6);
                if (!SetupDiGetDeviceInterfaceDetail(set, ref iface, detail, required, out required, ref data))
                {
                    return null;
                }
                return Marshal.PtrToStringUni(new IntPtr(detail.ToInt64() + 4));
            }
            finally
            {
                Marshal.FreeHGlobal(detail);
            }
        }

        public static List<UsbController> Dump()
        {
            List<UsbController> controllers = new List<UsbController>();
            Dictionary<string, DeviceNode> devices = DevicesByDriverKey();
            Guid hostGuid = HostControllerInterface;
            IntPtr set = SetupDiGetClassDevs(ref hostGuid, null, IntPtr.Zero, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
            if (set == IntPtr.Zero || set == new IntPtr(-1))
            {
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            }
            try
            {
                for (int index = 0; ; index++)
                {
                    SP_DEVICE_INTERFACE_DATA iface = new SP_DEVICE_INTERFACE_DATA();
                    iface.cbSize = Marshal.SizeOf(typeof(SP_DEVICE_INTERFACE_DATA));
                    if (!SetupDiEnumDeviceInterfaces(set, IntPtr.Zero, ref hostGuid, index, ref iface))
                    {
                        break;
                    }
                    SP_DEVINFO_DATA data = new SP_DEVINFO_DATA();
                    data.cbSize = Marshal.SizeOf(typeof(SP_DEVINFO_DATA));
                    UsbController controller = new UsbController();
                    controller.Ports = new List<UsbPort>();
                    controller.CompatibleIds = new string[0];
                    controller.BusNumber = -1;
                    controller.Address = -1;
                    controllers.Add(controller);
                    try
                    {
                        string path = InterfacePath(set, ref iface, ref data);
                        controller.InstanceId = InstanceId(set, ref data);
                        controller.Name = DisplayName(set, ref data, false);
                        controller.CompatibleIds = RegistryMultiString(set, ref data, SPDRP_COMPATIBLEIDS);
                        controller.Service = RegistryString(set, ref data, SPDRP_SERVICE);
                        controller.AcpiPath = PropertyString(set, ref data, 10);
                        controller.BusNumber = RegistryInt(set, ref data, SPDRP_BUSNUMBER);
                        controller.Address = RegistryInt(set, ref data, SPDRP_ADDRESS);
                        if (path == null)
                        {
                            controller.Error = "No device path for the controller.";
                            continue;
                        }
                        string rootHub;
                        using (SafeFileHandle handle = OpenDevice(path))
                        {
                            if (handle.IsInvalid)
                            {
                                controller.Error = "Could not open the controller (error " + Marshal.GetLastWin32Error() + ").";
                                continue;
                            }
                            rootHub = NameIoctl(handle, IOCTL_USB_GET_ROOT_HUB_NAME, 0, 4);
                        }
                        if (String.IsNullOrEmpty(rootHub))
                        {
                            controller.Error = "The controller has no root hub.";
                            continue;
                        }
                        controller.HubName = rootHub;
                        using (SafeFileHandle hub = OpenDevice(@"\\.\" + rootHub))
                        {
                            if (hub.IsInvalid)
                            {
                                controller.Error = "Could not open the root hub (error " + Marshal.GetLastWin32Error() + ").";
                                continue;
                            }
                            controller.PortCount = HubPortCount(hub);
                            for (int port = 1; port <= controller.PortCount; port++)
                            {
                                controller.Ports.Add(ReadPort(hub, port, devices, 0));
                            }
                        }
                    }
                    catch (Exception e)
                    {
                        controller.Error = e.Message;
                    }
                }
            }
            finally
            {
                SetupDiDestroyDeviceInfoList(set);
            }
            return controllers;
        }
    }
}
