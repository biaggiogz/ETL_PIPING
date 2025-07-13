const { ECSClient, RunTaskCommand, StopTaskCommand, DescribeTasksCommand, ListTasksCommand } = require('@aws-sdk/client-ecs');
const { ElasticLoadBalancingV2Client, RegisterTargetsCommand, DeregisterTargetsCommand } = require('@aws-sdk/client-elastic-load-balancing-v2');

const ecs = new ECSClient({ region: process.env.AWS_REGION });
const elbv2 = new ElasticLoadBalancingV2Client({ region: process.env.AWS_REGION });

exports.handler = async (event) => {
    const headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    };

    try {
        const { httpMethod, body } = event;
        
        if (httpMethod === 'GET') {
            return await getTaskStatus();
        } else if (httpMethod === 'POST') {
            const { action } = JSON.parse(body);
            
            if (action === 'start') {
                return await startTask();
            } else if (action === 'stop') {
                return await stopTask();
            }
        }
        
        return {
            statusCode: 400,
            headers,
            body: JSON.stringify({ error: 'Invalid action' })
        };
        
    } catch (error) {
        console.error('Error:', error);
        return {
            statusCode: 500,
            headers,
            body: JSON.stringify({ error: error.message })
        };
    }
};

async function getTaskStatus() {
    const listParams = {
        cluster: process.env.CLUSTER_NAME,
        serviceName: undefined,
        desiredStatus: 'RUNNING'
    };
    
    const listResult = await ecs.send(new ListTasksCommand(listParams));
    
    if (listResult.taskArns.length === 0) {
        return {
            statusCode: 200,
            headers: {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            body: JSON.stringify({ 
                status: 'STOPPED',
                taskCount: 0
            })
        };
    }
    
    const describeParams = {
        cluster: process.env.CLUSTER_NAME,
        tasks: listResult.taskArns
    };
    
    const describeResult = await ecs.send(new DescribeTasksCommand(describeParams));
    const task = describeResult.tasks[0];
    
    return {
        statusCode: 200,
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        body: JSON.stringify({
            status: task.lastStatus,
            taskCount: describeResult.tasks.length,
            taskArn: task.taskArn
        })
    };
}

async function startTask() {
    const params = {
        cluster: process.env.CLUSTER_NAME,
        taskDefinition: process.env.TASK_DEFINITION,
        launchType: 'FARGATE',
        networkConfiguration: {
            awsvpcConfiguration: {
                subnets: process.env.SUBNET_IDS.split(','),
                securityGroups: [process.env.SECURITY_GROUP_ID],
                assignPublicIp: 'ENABLED'
            }
        }
    };
    
    const result = await ecs.send(new RunTaskCommand(params));
    const task = result.tasks[0];
    
    // Wait for task to get IP address
    await new Promise(resolve => setTimeout(resolve, 10000));
    
    // Get task details to find IP
    const describeResult = await ecs.send(new DescribeTasksCommand({
        cluster: process.env.CLUSTER_NAME,
        tasks: [task.taskArn]
    }));
    
    const taskDetails = describeResult.tasks[0];
    console.log('Task details:', JSON.stringify(taskDetails, null, 2));
    const privateIp = taskDetails.attachments[0].details.find(d => d.name === 'privateIPv4Address');
    console.log('Private IP:', privateIp?.value);
    
    if (privateIp) {
        // Register with both target groups
        await elbv2.send(new RegisterTargetsCommand({
            TargetGroupArn: process.env.TARGET_GROUP_ARN_8081,
            Targets: [{ Id: privateIp.value, Port: 8081 }]
        }));
        
        await elbv2.send(new RegisterTargetsCommand({
            TargetGroupArn: process.env.TARGET_GROUP_ARN_5173,
            Targets: [{ Id: privateIp.value, Port: 5173 }]
        }));
    }
    
    return {
        statusCode: 200,
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        body: JSON.stringify({
            message: 'Task started',
            taskArn: task.taskArn
        })
    };
}

async function stopTask() {
    const listParams = {
        cluster: process.env.CLUSTER_NAME,
        desiredStatus: 'RUNNING'
    };
    
    const listResult = await ecs.send(new ListTasksCommand(listParams));
    
    if (listResult.taskArns.length === 0) {
        return {
            statusCode: 200,
            headers: {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            body: JSON.stringify({ message: 'No running tasks found' })
        };
    }
    
    const stopParams = {
        cluster: process.env.CLUSTER_NAME,
        task: listResult.taskArns[0]
    };
    
    await ecs.send(new StopTaskCommand(stopParams));
    
    return {
        statusCode: 200,
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        body: JSON.stringify({ message: 'Task stopped' })
    };
}