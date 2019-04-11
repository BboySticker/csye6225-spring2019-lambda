
import logging
import boto3
import uuid
import time
import json
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

# DynamoDB configuration
dynamodb = boto3.resource('dynamodb', region_name = 'us-east-1', endpoint_url = "http://dynamodb.us-east-1.amazonaws.com")
table = dynamodb.Table("email_token")
key_name = 'email_address'
attToken = 'token'
attTime = 'ttl'
TTL = 1 # minutes

# email configuration
AWS_REGION = "us-east-1"
SUBJECT = "Password Reset"
CHAR_SET = "UTF-8"
BODY_TEXT = "Please click following url to reset your password: (expires in 20 minutes)"
BODY_HTML = """<html>
<head></head>
<body>
    <h4>Password Reset</h4>
"""
client = boto3.client('ses', region_name=AWS_REGION)

# logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger("main") # set file name
logger = logging.getLogger(__name__) # TODO: using logger or not?


def email_handler(event, context):
    '''handler for aws lambda'''
    # get message from SNS
    try:
        msg = json.loads(event['Records'][0]['Sns']['Message'])
        email_address = msg['email']
        domain = msg['domain'] # set sender domain
    except Exception:
        logger.error("Parse SNS message error, do nothing and exit")
        return None

    print("Set sender domain: [ " + domain + " ] and get email: [ " + email_address + " ]")
    
    if (email_exists(email_address)):
        if (not(token_expired(email_address))):
            logger.warning("Email [ " + email_address + " ], token not expired")
            return None
  
    token = str(uuid.uuid4())
    save_item(email_address, token)
    logger.info("Email token saved to DynamoDB")
    send_email(email_address, token, domain)

    return None

def token_expired(email):
    '''true if token expired'''
    try:
        response = table.get_item(
            Key={
                key_name: email
            }
        )
    except ClientError:
        logger.error("fetch response failed, key name error in [ token_expired ]")
        exit(1)
        return False
    else:
        try:
            dbTime = response['Item'][attTime] # The time to live timestamp
        except KeyError:
            logger.error("key error in querying timstamp of email [ " + email + "]  in [ token_expired ]")
            exit(1)
            return False
        else:
            curr = int(time.time())
            if (curr >= dbTime):
                return True
            gap =  (dbTime - curr)/60
            logger.info("Time since last password reset request: " + str(TTL - int(gap)) + " minutes")
            return False
    
def email_exists(email):
    '''true if email record still in db'''
    try:
        response = table.query(
            KeyConditionExpression=Key(key_name).eq(email)
        )
    except ClientError:
        logger.error("fetch response failed, key name error in [ email_exists ]")
        exit(1)
        return False
    else:
        try:
            res = response['Items'] != []
        except KeyError:
            logger.error("key error in querying timstamp of email [ " + email + " ] in [ email_exists ]")
            exit(1)
            return False
        else:
            logger.info("Qeury email existance in DynamoDB, " + str(res))
            return res

def save_item(email, token):
    '''save item in db'''
    if (not(email_exists(email))):
        # create item
        try:
            response = table.put_item(
                Item={
                    key_name: email,
                    attToken: token,
                    attTime: int(time.time()) + TTL * 60
                }
            )
        except ClientError as e:
            logger.error("Error create item in [ save_item ]")
            exit(1)
            return
    else:
        # item exits in database, token expired
        try:
            response = table.update_item(
                Key={
                    key_name: email
                },
                UpdateExpression="set "+attToken+"=:to, "+attTime+"=:ti",
                ExpressionAttributeValues={
                    ':to': token,
                    ':ti': int(time.time()) + TTL * 60
                },
                ReturnValues="UPDATED_NEW"
            )
        except:
            logger.error("Error save item through updating in [ save_item ]")
        else:
            # logger.info("Email still in database, token not expired or not deleted")
            return



def send_email(email, token, domain):
    '''send email with password reset token'''
    try:
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    email,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHAR_SET,
                        'Data': BODY_HTML + "<p>" + BODY_TEXT + "<br/><br/>https://" + domain + "/reset?email=" + email + "&token=" + token + "</p></body></html>",
                    },
                    'Text': {
                        'Charset': CHAR_SET,
                        'Data': BODY_TEXT + "\nhttps://" + domain + "/reset?email=" + email + "&token=" + token,
                    },
                },
                'Subject': {
                    'Charset': CHAR_SET,
                    'Data': SUBJECT,
                },
            },
            Source="noreply@" + domain,
            # ConfigurationSetName=CONFIGURATION_SET,
        )
    except Exception as e:
        logger.error("Send email to receipient failed in [ send_email ]")
        logger.error(str(e))
        exit(1)
        return
    else:
        logger.info("Email sent, Message ID: [ " + response['MessageId'] + " ]")
        return


def create_table():
    pass


# # test code
# sim_msg = """{
# 	"domain": "csye6225-spring2019-liulei1.me",
# 	"email": "liulei6696@gmail.com"
# }
# """

# # get message from SNS
# try:
#     msg = json.loads(sim_msg)
#     email_address = msg['email']
#     SENDER_DOMAIN = msg['domain'] # set sender
# except Exception:
#     logger.error("Parse SNS message error, do nothing and exit")


# logger.info("Get email: [ " + email_address + " ] and set sender: [ " + SENDER_DOMAIN + " ]")
    
# if (email_exists(email_address)):
#     if (not(token_expired(email_address))):
#         logger.warning("email [ " + email_address + " ], token not expired")
# else:
#     token = str(uuid.uuid4())
#     save_item(email_address, token)
#     logger.info("Email token saved to DynamoDB")
#     send_email(email_address, token)
