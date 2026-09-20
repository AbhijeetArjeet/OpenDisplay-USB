#include "OpenDisplayIdd.h"

NTSTATUS OpenDisplayMonitorAssignSwapChain(
    _In_ IDDCX_MONITOR MonitorObject,
    _In_ const IDARG_IN_SETSWAPCHAIN* pInArgs
)
{
    MonitorContext* monitorCtx = WdfObjectGetTypedContext(MonitorObject, MonitorContext);

    WDF_OBJECT_ATTRIBUTES attr;
    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&attr, SwapChainContext);

    // Initialize swapchain context and save event handles
    SwapChainContext* swapCtx = nullptr;
    IDDCX_SWAPCHAIN swapChain = pInArgs->hSwapChain;

    // Set processing device
    IDARG_IN_SETSWAPCHAINDEVICE setDeviceArgs = {};
    setDeviceArgs.pDevice = nullptr; // Uses default D3D11 device
    IddCxSwapChainSetDevice(swapChain, &setDeviceArgs);

    return STATUS_SUCCESS;
}

NTSTATUS OpenDisplayMonitorUnassignSwapChain(
    _In_ IDDCX_MONITOR MonitorObject
)
{
    UNREFERENCED_PARAMETER(MonitorObject);
    return STATUS_SUCCESS;
}
