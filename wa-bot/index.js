const { Client, LocalAuth } = require(
    'whatsapp-web.js'
);

const qrcode = require(
    'qrcode-terminal'
);

const axios = require(
    'axios'
);

const RAG_API_URL =
    'http://127.0.0.1:8000/query';


// =========================
// ALLOWED GROUPS
// =========================

const ALLOWED_GROUPS = [

    'uncz',

    'bbc',

    'apateu pateu'

];


// =========================
// ALLOWED DMS
// Use display names exactly
// =========================

const ALLOWED_USERS = [
];


// =========================
// CLIENT
// =========================

const client = new Client({

    authStrategy:

        new LocalAuth({

            clientId:
                'unczbot'

        }),

    puppeteer: {

        headless: false,

        args: [

            '--no-sandbox',

            '--disable-setuid-sandbox',

            '--disable-dev-shm-usage'

        ]

    }

});


// =========================
// EVENTS
// =========================

client.on(

    'qr',

    qr => {

        console.log(
            '\nSCAN QR:\n'
        );

        qrcode.generate(
            qr,
            {
                small:true
            }
        );

    }

);

client.on(

    'authenticated',

    () => {

        console.log(
            'AUTH OK'
        );

    }

);

client.on(

    'auth_failure',

    msg => {

        console.log(

            'AUTH FAIL:',

            msg

        );

    }

);

client.on(

    'disconnected',

    reason => {

        console.log(

            'DISCONNECTED:',

            reason

        );

    }

);

client.on(

    'ready',

    () => {

        console.log(
            '\nWHATSAPP READY\n'
        );

    }

);


// =========================
// MESSAGE HANDLER
// =========================

client.on(

    'message_create',

    async msg => {

        try {

            if (
                !msg.body
            ) return;

            if (
                msg.fromMe
            ) return;


            const chat =

                await msg.getChat();

            let person = '';


            // =========================
            // GROUP CHECK
            // =========================

            if (

                chat.isGroup

            ) {

                const groupName =

                    chat.name

                    ?

                    chat.name

                    .toLowerCase()

                    .trim()

                    :

                    '';

                if (

                    !ALLOWED_GROUPS

                    .includes(

                        groupName

                    )

                ) {

                    return;

                }

                if (

                    msg.author

                ) {

                    const authorContact =

                        await client

                        .getContactById(

                            msg.author

                        );

                    person =

                        (

                            authorContact.pushname

                            ||

                            authorContact.name

                            ||

                            ''

                        )

                        .toLowerCase()

                        .trim();

                }

                if (

                    !person

                ) {

                    person =

                        groupName

                        ||

                        'group';

                }

                console.log(

                    `\nGROUP:`,

                    chat.name,

                    'FROM:',

                    person

                );

            }


            // =========================
            // DM CHECK
            // =========================

            else {

                const contact =

                    await msg.getContact();

                person =

                    (

                        contact.pushname

                        ||

                        contact.name

                        ||

                        ''

                    )

                    .toLowerCase()

                    .trim();


                const allowed =

                    ALLOWED_USERS

                    .map(

                        x =>

                        x

                        .toLowerCase()

                    )

                    .includes(

                        person

                    );


                if (

                    !allowed

                ) {

                    return;

                }


                console.log(

                    `\nDM:`,

                    person

                );

            }


            console.log(

                'MESSAGE:',

                msg.body

            );


            // =========================
            // RAG CALL
            // =========================

            const response =

                await axios.post(

                    RAG_API_URL,

                    {

                        query:

                            person + "asked: " + msg.body

                    },

                    {

                        headers: {

                            'Content-Type':

                                'application/json'

                        },

                        timeout:

                            60000

                    }

                );


            if (

                response.data

                &&

                response.data.answer

            ) {

                const reply =

                    response

                    .data

                    .answer

                    .trim();


                if (

                    reply

                ) {

                    await msg.reply(
                        'cheji bt: ' + reply
                    );

                    console.log(

                        'REPLIED:',

                        reply

                    );

                }

            }

            else {

                console.warn(

                    'BAD API RESPONSE',

                    response.data

                );

            }

        }

        catch(error) {

            console.error(

                '\nERROR:\n',

                error.message

                ||

                error

            );

        }

    }

);


// =========================
// START
// =========================

console.log(
    'STARTING BOT'
);

client.initialize();