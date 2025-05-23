# Maintenance without downtime

A {{ ydb-short-name }} cluster periodically needs maintenance, such as upgrading its version or replacing broken disks. Maintenance can cause a cluster or its databases to become unavailable due to:

- Going beyond the expectations of the affected [storage groups](../../concepts/glossary.md#storage-groups) failure model.
- Going beyond the expectations of the [State Storage](../../reference/configuration/index.md#domains-state) failure model.
- Lack of computational resources due to stopping too many [dynamic nodes](../../concepts/glossary.md#dynamic-node).

To avoid such situations, {{ ydb-short-name }} has a system [tablet](../../concepts/glossary.md#tablet) that monitors the state of the cluster - the *Cluster Management System (CMS)*. The CMS allows you to answer the question of whether a {{ ydb-short-name }} node or host running {{ ydb-short-name }} nodes can be safely taken out for maintenance. To do this, create a [maintenance task](#maintenance-task) in the CMS and specify in it to acquire exclusive locks on the nodes or hosts that will be involved in the maintenance. The cluster components on which the locks are acquired are considered unavailable from the CMS perspective and can be safely engaged in maintenance. The CMS will [check](#checking-algorithm) the current state of the cluster and acquire locks only if the maintenance complies with the [availability mode](#availability-mode) and [unavailable node limits](#unavailable-node-limits).

{% note warning "Failures during maintenance" %}

During maintenance activities whose safety is guaranteed by the CMS, failures unrelated to those activities may occur in the cluster. If the failures threaten the cluster's availability, urgently aborting the maintenance can help mitigate the risk of cluster downtime.

{% endnote %}

## Maintenance task {#maintenance-task}

A *maintenance task* is a set of *actions* that the user asks the CMS to perform for safe maintenance.

Supported actions:

- Acquiring an exclusive lock on a cluster component (node, host, or disk).

Actions in a task are divided into groups. Actions from the same group are performed atomically. Currently, groups can consist of only one action.

If an action cannot be performed at the time of the request, the CMS informs you of the reason and time it is worth *refreshing* the task and sets the action status to *pending*. When the task is refreshed, the CMS attempts to perform the pending actions again.

*Performed* actions have a deadline after which they are considered *completed* and stop affecting the cluster. For example, an exclusive lock is released. An action can be completed early.

{% note info "Protracted maintenance" %}

If maintenance continues after the actions performed to make it safe have been completed, this is considered a failure in the cluster.

{% endnote %}

Completed actions are automatically removed from the task.

### Availability mode {#availability-mode}

In a maintenance task, you need to specify the cluster's availability mode to comply with when checking whether actions can be performed. The following modes are supported:

- **Strong**: a mode that minimizes the risk of availability loss.
    - No more than one unavailable [VDisk](../../concepts/glossary.md#vdisk) is allowed in each affected storage group.
    - No more than one unavailable State Storage ring is allowed.
- **Weak**: a mode that does not allow exceeding the failure model.

  - For affected storage groups with the [block-4-2](../../reference/configuration/index.md#reliability) scheme, no more than two unavailable VDisks are allowed.
  - For affected storage groups with the [mirror-3-dc](../../reference/configuration/index.md#reliability) scheme, up to four unavailable VDisks are allowed, three of which must be in the same data center.
  - No more than `(nto_select - 1) / 2` unavailable State Storage rings are allowed.

- **Force**: a forced mode, the failure model is ignored. *Not recommended for use.*

### Priority {#priority}

You can specify the priority of a maintenance task. A lower value means a higher priority.

The task's actions cannot be performed until all conflicting actions from tasks with a higher priority are completed. Tasks with the same priority have no advantage over each other.

## Unavailable node limits {#unavailable-node-limits}

In the CMS configuration, you can configure limits on the number of unavailable nodes for a database (tenant) or the cluster as a whole. Relative and absolute limits are supported.

By default, each database and the cluster as a whole are allowed to have no more than 13% unavailable nodes.

## Checking algorithm {#checking-algorithm}

To check if the actions of a maintenance task can be performed, the CMS sequentially goes through each action group in the task and checks the action from the group:

- If the action's object is a host, the CMS checks whether the action can be performed with all nodes running on the host.
- If the action's object is a node, the CMS checks:

  - Whether there is a lock on the node.
  - Whether it's possible to lock the node according to the limits of unavailable nodes.
  - Whether it's possible to lock all VDisks of the node according to the availability mode.
  - Whether it's possible to lock the State Storage ring of the node according to the availability mode.
  - Whether it's possible to lock the node according to the limit of unavailable nodes on which cluster system tablets can run.

- If the action's object is a disk, the CMS checks:

  - Whether there is a lock on the disk.
  - Whether it's possible to lock all VDisks of the disk according to the availability mode.

The action can be performed if the checks are successful, and temporary locks are acquired on the checked nodes, hosts, or disks. The CMS then considers the next group of actions. Temporary locks help to understand whether the actions requested in different groups conflict with each other. Once the check is complete, the temporary locks are released.

## Examples {#examples}

The [ydbops](../../reference/ydbops/index.md) utility tool uses CMS for cluster maintenance without downtime. You can also use the CMS directly through the [gRPC API](https://github.com/ydb-platform/ydb/blob/main/ydb/public/api/grpc/draft/ydb_maintenance_v1.proto).

### Rolling restart {##rolling-restart}

To perform a rolling restart of the entire cluster, you can use the command:

```bash
$ ydbops restart
```

The default availability mode is `strong`. This mode minimizes the risk of availability loss. Use the `--availability-mode` parameter to override the default availability mode.

The `ydbops` utility will automatically create a maintenance task to restart the entire cluster using the given availability mode. As it progresses, the `ydbops` will refresh the maintenance task and acquire exclusive locks on the nodes in the CMS until all nodes are restarted.

### Take out a host for maintenance {#host-maintenance}

To take out a host for maintenance, follow these steps:

1. Create a maintenance task using the command:

    ```bash
    $ ydbops maintenance create --hosts=<fqdn> --duration=<seconds>
    ```

    This command creates a maintenance task that will acquire an exclusive lock for `<seconds>` seconds on the host with the fully qualified domain name `<fqdn>`.
2. After creating a task, refresh its state until the lock is taken, using the command:

    ```bash
    $ ydbops maintenance refresh --task-id=<id>
    ```

    This command refreshes the task with identifier `<id>` and attempts to acquire the required lock. When a `PERFORMED` response is received, proceed to the next step.
3. Perform host maintenance while the lock is acquired.
4. After the maintenance is complete, release the lock using the command:

    ```bash
    $ ydbops maintenance complete --task-id=<id> --hosts=<fqdn>
    ```
