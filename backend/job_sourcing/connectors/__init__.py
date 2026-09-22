from job_sourcing.connectors.base import IJobConnector, JobOfferDTO, register_connector
from job_sourcing.connectors.remotive.connector import RemotiveConnector
from job_sourcing.connectors.arbeitnow.connector import ArbeitnowConnector
from job_sourcing.connectors.jobicy.connector import JobicyConnector
from job_sourcing.connectors.themuse.connector import TheMuseConnector
from job_sourcing.connectors.bundesagentur.connector import BundesagenturConnector
from job_sourcing.connectors.linkedin.connector import LinkedInConnector

# Register free official API connectors
# Keep ONLY Arbeitnow active for job sourcing
# register_connector("remotive", RemotiveConnector())
register_connector("arbeitnow", ArbeitnowConnector())
# register_connector("jobicy", JobicyConnector())
# register_connector("themuse", TheMuseConnector())
# register_connector("bundesagentur", BundesagenturConnector())

# Register LinkedIn connector (public guest API)
# register_connector("linkedin", LinkedInConnector())



