// PeopleCounterUDPModule.cpp
#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class FPeopleCounterUDPModule : public IModuleInterface
{
public:
	virtual void StartupModule() override
	{
		// Intenzionalmente vuoto: niente allocazioni globali, niente socket.
	}

	virtual void ShutdownModule() override
	{
		// Intenzionalmente vuoto.
	}
};

IMPLEMENT_MODULE(FPeopleCounterUDPModule, PeopleCounterUDP)
