#pragma once

#include <windows.h>
#include <wdf.h>
#include <iddcx.h>
#include <dxgi1_5.h>
#include <d3d11_2.h>

// Context structures
struct DriverContext
{
    // Empty for driver level
};

struct DeviceContext
{
    IDDCX_ADAPTER Adapter;
};

struct MonitorContext
{
    IDDCX_MONITOR Monitor;
    HANDLE ProcessingThread;
    HANDLE TerminateEvent;
};

struct SwapChainContext
{
    IDDCX_SWAPCHAIN SwapChain;
    HANDLE BufferAvailableEvent;
};

WDF_DECLARE_CONTEXT_TYPE(DeviceContext);
WDF_DECLARE_CONTEXT_TYPE(MonitorContext);
WDF_DECLARE_CONTEXT_TYPE(SwapChainContext);

// Function declarations
extern "C" DRIVER_INITIALIZE DriverEntry;

EVT_WDF_DRIVER_DEVICE_ADD OpenDisplayDeviceAdd;
EVT_WDF_DEVICE_D0_ENTRY OpenDisplayDeviceD0Entry;

// IddCx adapter callbacks
EVT_IDD_CX_ADAPTER_INIT_FINISHED OpenDisplayAdapterInitFinished;
EVT_IDD_CX_ADAPTER_COMMIT_MODES OpenDisplayAdapterCommitModes;

// IddCx monitor callbacks
EVT_IDD_CX_MONITOR_GET_DEFAULT_DESCRIPTION_MODES OpenDisplayMonitorGetDefaultModes;
EVT_IDD_CX_MONITOR_QUERY_TARGET_MODES OpenDisplayMonitorQueryModes;
EVT_IDD_CX_MONITOR_ASSIGN_SWAPCHAIN OpenDisplayMonitorAssignSwapChain;
EVT_IDD_CX_MONITOR_UNASSIGN_SWAPCHAIN OpenDisplayMonitorUnassignSwapChain;
