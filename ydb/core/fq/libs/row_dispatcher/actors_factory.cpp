#include <ydb/core/fq/libs/row_dispatcher/actors_factory.h>

#include <ydb/core/fq/libs/row_dispatcher/topic_session.h>

namespace NFq::NRowDispatcher {


struct TActorFactory : public IActorFactory {
    TActorFactory() {}

    NActors::TActorId RegisterTopicSession(
        const NConfig::TRowDispatcherConfig& config,
        NActors::TActorId rowDispatcherActorId,
        ui32 partitionId,
        NYdb::TDriver driver,
        std::shared_ptr<NYdb::ICredentialsProviderFactory> credentialsProviderFactory) const override {

        auto actorPtr = NFq::NewTopicSession(
            config,
            rowDispatcherActorId,
            partitionId,
            driver,
            credentialsProviderFactory
        );
        return NActors::TlsActivationContext->ExecutorThread.RegisterActor(actorPtr.release(), NActors::TMailboxType::HTSwap, Max<ui32>());
    }
};

IActorFactory::TPtr CreateActorFactory() {
    return MakeIntrusive<TActorFactory>();
}

}
