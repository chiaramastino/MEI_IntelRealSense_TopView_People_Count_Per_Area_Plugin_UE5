#include "UDPJsonReceiverComponent.h"

#include "Sockets.h"
#include "SocketSubsystem.h"
#include "IPAddress.h"
#include "Common/UdpSocketBuilder.h"
#include "HAL/RunnableThread.h"
#include "Misc/ScopeLock.h"
#include "Common/UdpSocketBuilder.h"
#include "Interfaces/IPv4/IPv4Endpoint.h"   // << questa riga
#include "Async/Async.h"            // 🔧 per AsyncTask

DEFINE_LOG_CATEGORY_STATIC(LogPeopleCounterUDP_RX, Log, All);

UUDPJsonReceiverComponent::UUDPJsonReceiverComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

void UUDPJsonReceiverComponent::BeginPlay()
{
    Super::BeginPlay();
    if (bAutoStart)
    {
        StartReceiver();
    }
}

void UUDPJsonReceiverComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    StopReceiver();
    Super::EndPlay(EndPlayReason);
}

bool UUDPJsonReceiverComponent::CreateSocket()
{
    if (ListenSocket) return true;

    bool bIsValid = false;
    TSharedRef<FInternetAddr> Addr = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateInternetAddr();
    Addr->SetIp(*ListenAddress, bIsValid);
    if (!bIsValid)
    {
        UE_LOG(LogPeopleCounterUDP_RX, Error, TEXT("Invalid ListenAddress: %s"), *ListenAddress);
        return false;
    }
    Addr->SetPort(ListenPort);

    ListenSocket = FUdpSocketBuilder(TEXT("PeopleCounterUDP_RX"))
        .AsNonBlocking()
        .AsReusable()
        .BoundToEndpoint(FIPv4Endpoint(Addr))
        .WithReceiveBufferSize(2 * 1024 * 1024);

    if (!ListenSocket)
    {
        UE_LOG(LogPeopleCounterUDP_RX, Error, TEXT("Failed to create UDP listen socket."));
        return false;
    }
    return true;
}

void UUDPJsonReceiverComponent::DestroySocket()
{
    if (SocketReceiver)
    {
        SocketReceiver->Stop();
        delete SocketReceiver;
        SocketReceiver = nullptr;
    }
    if (ListenSocket)
    {
        ListenSocket->Close();
        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ListenSocket);
        ListenSocket = nullptr;
    }
}

bool UUDPJsonReceiverComponent::StartReceiver()
{
    if (bRunning) return true;
    if (!CreateSocket()) return false;

    SocketReceiver = new FUdpSocketReceiver(ListenSocket, FTimespan::FromMilliseconds(2), TEXT("PeopleCounterUDP_RX"));
    SocketReceiver->OnDataReceived().BindUObject(this, &UUDPJsonReceiverComponent::HandlePacket);
    SocketReceiver->Start();

    bRunning = true;
    UE_LOG(LogPeopleCounterUDP_RX, Log, TEXT("UDP Receiver started on %s:%d"), *ListenAddress, ListenPort);
    return true;
}

void UUDPJsonReceiverComponent::StopReceiver()
{
    if (!bRunning) return;
    bRunning = false;
    DestroySocket();
    UE_LOG(LogPeopleCounterUDP_RX, Log, TEXT("UDP Receiver stopped"));
}

void UUDPJsonReceiverComponent::HandlePacket(const FArrayReaderPtr& Data, const FIPv4Endpoint& Endpoint)
{
    FString JsonStr;
    JsonStr.Empty();

    // Copia sicura dei bytes
    TArray<uint8> Bytes;
    Bytes.SetNumUninitialized(Data->Num());
    FMemory::Memcpy(Bytes.GetData(), Data->GetData(), Data->Num());

    // UTF-8 -> FString
    FUTF8ToTCHAR Conv(reinterpret_cast<const ANSICHAR*>(Bytes.GetData()), Bytes.Num());
    JsonStr = FString(Conv.Length(), Conv.Get());

    if (bLogPackets)
    {
        UE_LOG(LogPeopleCounterUDP_RX, Verbose, TEXT("RX from %s: %s"), *Endpoint.ToString(), *JsonStr);
    }

    // Dispatch su GameThread
    AsyncTask(ENamedThreads::GameThread, [this, JsonStr]()
    {
        OnJsonReceived.Broadcast(JsonStr);
    });
}
