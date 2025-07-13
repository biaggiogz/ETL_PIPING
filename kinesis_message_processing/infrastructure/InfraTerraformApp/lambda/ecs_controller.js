const { ECSClient, UpdateServiceCommand, DescribeServicesCommand } = require('@aws-sdk/client-ecs');

const ecs = new ECSClient({ region: process.env.AWS_REGION });

exports.handler = async (event) => {
    console.log('Lambda invoked with event:', JSON.stringify(event, null, 2));
    console.log('Environment variables:', {
        CLUSTER_NAME: process.env.CLUSTER_NAME,
        SERVICE_NAME: process.env.SERVICE_NAME,
    });

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
            console.log('Received action:', action);

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
    console.log('Starting service - setting desiredCount to 1');
    console.log('Cluster:', process.env.CLUSTER_NAME);
    console.log('Service:', process.env.SERVICE_NAME);

    const updateResult = await ecs.send(new UpdateServiceCommand({
        cluster: process.env.CLUSTER_NAME,
        service: process.env.SERVICE_NAME,
        desiredCount: 1,
        forceNewDeployment: false

    }));

    console.log('Service update result:', JSON.stringify(updateResult.service, null, 2));
    console.log('Service started successfully');

    return {
        statusCode: 200,
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        body: JSON.stringify({
            message: 'Service started',
            serviceName: updateResult.service.serviceName,
            desiredCount: updateResult.service.desiredCount
        })
    };
}

async function stopTask() {
    console.log('Stopping task - setting desiredCount to 0');
    console.log('Cluster:', process.env.CLUSTER_NAME);
    console.log('Service:', process.env.SERVICE_NAME);

    await ecs.send(new UpdateServiceCommand({
        cluster: process.env.CLUSTER_NAME,
        service: process.env.SERVICE_NAME,
        desiredCount: 0,
        forceNewDeployment: false

    }));

    console.log('Service stopped successfully');

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