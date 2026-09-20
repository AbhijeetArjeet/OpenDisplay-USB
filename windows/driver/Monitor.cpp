#include "OpenDisplayIdd.h"

// Standard synthetic 1080p EDID block (128 bytes)
static const BYTE s_KnownEdidBlock[] = {
    0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x38, 0x24, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00,
    0x01, 0x1E, 0x01, 0x04, 0xA5, 0x34, 0x20, 0x78, 0x3B, 0xEE, 0x91, 0xA3, 0x54, 0x4C, 0x99, 0x26,
    0x0F, 0x50, 0x54, 0xA5, 0x4B, 0x00, 0x71, 0x4F, 0x81, 0x80, 0xD1, 0xC0, 0x01, 0x01, 0x01, 0x01,
    0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x02, 0x3A, 0x80, 0x18, 0x71, 0x38, 0x2D, 0x40, 0x58, 0x2C,
    0x45, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1E, 0x00, 0x00, 0x00, 0xFD, 0x00, 0x38, 0x4B, 0x1E,
    0x53, 0x0F, 0x00, 0x0A, 0x20, 0x20, 0x20, 0x20, 0x20, 0x20, 0x00, 0x00, 0x00, 0xFC, 0x00, 0x4F,
    0x70, 0x65, 0x6E, 0x44, 0x69, 0x73, 0x70, 0x6C, 0x61, 0x79, 0x0A, 0x20, 0x00, 0x00, 0x00, 0xFF,
    0x00, 0x4F, 0x44, 0x53, 0x50, 0x30, 0x30, 0x31, 0x0A, 0x20, 0x20, 0x20, 0x20, 0x20, 0x00, 0xBE
};

NTSTATUS OpenDisplayCreateMonitor(
    _In_ IDDCX_ADAPTER Adapter,
    _Out_ IDDCX_MONITOR* pMonitor
)
{
    IDDCX_MONITOR_INFO monitorInfo = {};
    monitorInfo.Size = sizeof(monitorInfo);
    monitorInfo.MonitorType = DISPLAYCONFIG_OUTPUT_TECHNOLOGY_DISPLAYPORT_EMBEDDED;
    monitorInfo.ConnectorIndex = 0;
    monitorInfo.MonitorDescription.Size = sizeof(monitorInfo.MonitorDescription);
    monitorInfo.MonitorDescription.Type = IDDCX_MONITOR_DESCRIPTION_TYPE_EDID;
    monitorInfo.MonitorDescription.DataSize = sizeof(s_KnownEdidBlock);
    monitorInfo.MonitorDescription.pData = const_cast<BYTE*>(s_KnownEdidBlock);

    IDARG_IN_MONITORCREATE createArgs = {};
    createArgs.ObjectAttributes = nullptr;
    createArgs.pMonitorInfo = &monitorInfo;

    IDARG_OUT_MONITORCREATE createOut = {};
    NTSTATUS status = IddCxMonitorCreate(Adapter, &createArgs, &createOut);
    if (NT_SUCCESS(status))
    {
        *pMonitor = createOut.MonitorObject;
    }
    return status;
}

NTSTATUS OpenDisplayMonitorGetDefaultModes(
    _In_ IDDCX_MONITOR MonitorObject,
    _In_ const IDARG_IN_GETDEFAULTDESCRIPTIONMODES* pInArgs,
    _Out_ IDARG_OUT_GETDEFAULTDESCRIPTIONMODES* pOutArgs
)
{
    UNREFERENCED_PARAMETER(MonitorObject);
    UNREFERENCED_PARAMETER(pInArgs);
    UNREFERENCED_PARAMETER(pOutArgs);
    return STATUS_SUCCESS;
}

NTSTATUS OpenDisplayMonitorQueryModes(
    _In_ IDDCX_MONITOR MonitorObject,
    _In_ const IDARG_IN_QUERYTARGETMODES* pInArgs,
    _Out_ IDARG_OUT_QUERYTARGETMODES* pOutArgs
)
{
    UNREFERENCED_PARAMETER(MonitorObject);
    UNREFERENCED_PARAMETER(pInArgs);
    UNREFERENCED_PARAMETER(pOutArgs);
    return STATUS_SUCCESS;
}
