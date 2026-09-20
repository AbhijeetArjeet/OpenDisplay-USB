#include "OpenDisplayIdd.h"

NTSTATUS OpenDisplayDeviceAdd(
    _In_ WDFDRIVER Driver,
    _Inout_ PWDFDEVICE_INIT DeviceInit
)
{
    UNREFERENCED_PARAMETER(Driver);

    // Initialize IddCx device attributes
    NTSTATUS status = IddCxDeviceInitConfig(DeviceInit, nullptr);
    if (!NT_SUCCESS(status))
    {
        return status;
    }

    WDF_OBJECT_ATTRIBUTES attr;
    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&attr, DeviceContext);

    WDFDEVICE device;
    status = WdfDeviceCreate(&DeviceInit, &attr, &device);
    if (!NT_SUCCESS(status))
    {
        return status;
    }

    status = IddCxDeviceInitialize(device);
    if (!NT_SUCCESS(status))
    {
        return status;
    }

    // Configure IddCx adapter
    IDDCX_ADAPTER_CAPS adapterCaps = {};
    adapterCaps.Size = sizeof(adapterCaps);
    adapterCaps.Flags = IDDCX_ADAPTER_FLAGS_CAN_USE_MOVE_RECTS;
    adapterCaps.MaxMonitorsSupported = 1;

    IDDCX_ADAPTER_INIT_FINISHED initFinishedCallback = OpenDisplayAdapterInitFinished;
    IDDCX_ADAPTER_COMMIT_MODES commitModesCallback = OpenDisplayAdapterCommitModes;

    IDARG_IN_ADAPTER_INIT adapterInit = {};
    adapterInit.pCaps = &adapterCaps;
    adapterInit.ObjectAttributes = nullptr;

    IDARG_OUT_ADAPTER_INIT adapterOut = {};
    status = IddCxAdapterInit(&adapterInit, &adapterOut);

    DeviceContext* devCtx = WdfObjectGetTypedContext(device, DeviceContext);
    devCtx->Adapter = adapterOut.AdapterObject;

    return status;
}

NTSTATUS OpenDisplayAdapterInitFinished(
    _In_ IDDCX_ADAPTER AdapterObject,
    _In_ const IDARG_IN_ADAPTER_INIT_FINISHED* pInArgs
)
{
    UNREFERENCED_PARAMETER(AdapterObject);
    UNREFERENCED_PARAMETER(pInArgs);
    return STATUS_SUCCESS;
}

NTSTATUS OpenDisplayAdapterCommitModes(
    _In_ IDDCX_ADAPTER AdapterObject,
    _In_ const IDARG_IN_COMMITMODES* pInArgs
)
{
    UNREFERENCED_PARAMETER(AdapterObject);
    UNREFERENCED_PARAMETER(pInArgs);
    return STATUS_SUCCESS;
}
