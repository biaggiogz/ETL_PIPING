const { ECSClient, UpdateServiceCommand, DescribeServicesCommand } = require('@aws-sdk/client-ecs');

const ecs = new ECSClient({ region: process.env.AWS_REGION });

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
    const result = await ecs.send(new DescribeServicesCommand({
        cluster: process.env.CLUSTER_NAME,
        services: [process.env.SERVICE_NAME]
    }));
    
    const service = result.services[0];
    let status;
    
    if (service.desiredCount === 0) {
        status = 'STOPPED';
    } else if (service.runningCount === service.desiredCount) {
        status = 'RUNNING';
    } else {
        status = 'PENDING';
    }
    
    return {
        statusCode: 200,
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        body: JSON.stringify({
            status,
            taskCount: service.runningCount
        })
    };
}

async function startTask() {
    await ecs.send(new UpdateServiceCommand({
        cluster: process.env.CLUSTER_NAME,
        service: process.env.SERVICE_NAME,
        desiredCount: 1
    }));
    
    return {
        statusCode: 200,
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        body: JSON.stringify({
            message: 'Service started'
        })
    };
}

async function stopTask() {
    await ecs.send(new UpdateServiceCommand({
        cluster: process.env.CLUSTER_NAME,
        service: process.env.SERVICE_NAME,
        desiredCount: 0
    }));
    
    return {
        statusCode: 200,
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        body: JSON.stringify({
            message: 'Service stopped'
        })
    };
}