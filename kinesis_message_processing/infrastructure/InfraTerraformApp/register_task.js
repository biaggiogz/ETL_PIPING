const { ECSClient, DescribeTasksCommand, ListTasksCommand } = require('@aws-sdk/client-ecs');
const { ElasticLoadBalancingV2Client, RegisterTargetsCommand } = require('@aws-sdk/client-elastic-load-balancing-v2');

const ecs = new ECSClient({ region: 'us-east-1' });
const elbv2 = new ElasticLoadBalancingV2Client({ region: 'us-east-1' });

async function registerExistingTask() {
    // Get running tasks
    const listResult = await ecs.send(new ListTasksCommand({
        cluster: 'perspective-kinesis-cluster',
        desiredStatus: 'RUNNING'
    }));
    
    if (listResult.taskArns.length === 0) {
        console.log('No running tasks found');
        return;
    }
    
    // Get task details
    const describeResult = await ecs.send(new DescribeTasksCommand({
        cluster: 'perspective-kinesis-cluster',
        tasks: listResult.taskArns
    }));
    
    const task = describeResult.tasks[0];
    const privateIp = task.attachments[0].details.find(d => d.name === 'privateIPv4Address');
    
    if (privateIp) {
        console.log(`Registering task IP: ${privateIp.value}`);
        
        // Register with target groups
        await elbv2.send(new RegisterTargetsCommand({
            TargetGroupArn: 'arn:aws:elasticloadbalancing:us-east-1:881490115226:targetgroup/perspective-kinesis-tg-8081/4cde6ec524b442fb',
            Targets: [{ Id: privateIp.value, Port: 8081 }]
        }));
        
        await elbv2.send(new RegisterTargetsCommand({
            TargetGroupArn: 'arn:aws:elasticloadbalancing:us-east-1:881490115226:targetgroup/perspective-kinesis-tg-5173/79a9e495095e92ae',
            Targets: [{ Id: privateIp.value, Port: 5173 }]
        }));
        
        console.log('Registered with both target groups');
        
        console.log('Task registered successfully');
    }
}

registerExistingTask().catch(console.error);