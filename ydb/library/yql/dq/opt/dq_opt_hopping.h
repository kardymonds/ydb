#pragma once

#include <ydb/library/yql/dq/expr_nodes/dq_expr_nodes.h>

#include <util/datetime/base.h>

namespace NYql::NDq::NHopping {

NNodes::TMaybeNode<NNodes::TExprBase> RewriteAsHoppingWindow(
    const NNodes::TExprBase node,
    TExprContext& ctx,
    const NNodes::TDqConnection& input,
    bool analyticsHopping,
    TDuration lateArrivalDelay,
    bool defaultWatermarksMode,
    bool asyncActor);

} // namespace NYql::NDq::NHopping
