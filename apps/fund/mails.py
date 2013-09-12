from babel.dates import format_date
from babel.numbers import format_currency
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.template import Context
from django.utils.translation import ugettext as _
from celery import task


@task
def mail_new_voucher(voucher, *args, **kwargs):
    # TODO: Put this in config
    system_email = 'giftcards@1procentclub.nl'
    server = Site.objects.get_current().domain
    if server == 'localhost:8000':
        server = 'http://' + server
    else:
        server = 'https://' + server

    subject = _(u'You received a 1%GIFTCARD!')
    text_content = _(u'You received a 1%GIFTCARD with this code:') + ' ' + voucher.code.upper()
    context = Context({'voucher': voucher, 'server': server})
    html_content = get_template('voucher_new.mail.html').render(context)
    msg = EmailMultiAlternatives(subject=subject, body=text_content, from_email=system_email,
                                 to=[voucher.receiver_email], cc=[voucher.sender_email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()


@task
def mail_voucher_redeemed(voucher, *args, **kwargs):
    # TODO: Put this in config
    system_email = 'giftcards@1procentclub.nl'
    server = 'https://' + Site.objects.get_current().domain

    subject = voucher.receiver_name + ' ' + _(u'has supported a 1%PROJECT using your 1%GIFTCARD')
    text_content = voucher.receiver_name + ' ' + _(u'has supported a 1%PROJECT using your 1%GIFTCARD')
    context = Context({'voucher': voucher, 'server': server})
    html_content = get_template('voucher_redeemed.mail.html').render(context)
    msg = EmailMultiAlternatives(subject=subject, body=text_content, from_email=system_email,
                                 to=[voucher.receiver_email], cc=[voucher.sender_email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()


@task
def mail_custom_voucher_request(voucher_request, *args, **kwargs):
    # TODO: Put this in config
    #system_email = 'giftcards@1procentclub.nl'
    system_email = 'loek@1procentclub.nl'
    server = 'https://' + Site.objects.get_current().domain

    subject = voucher_request.contact_name + ' ' + _(u'has a custom 1%GIFTCARD request')
    text_content = voucher_request.contact_name + ' ' + _(u'has a custom 1%GIFTCARD request')
    context = Context({'voucher_request': voucher_request, 'server': server})
    html_content = get_template('custom_voucher_request.mail.html').render(context)
    msg = EmailMultiAlternatives(subject=subject, body=text_content, from_email=voucher_request.contact_email,
                                 to=[system_email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()

@task
def mail_monthly_donation_processed_notification(recurring_payment, recurring_order):
    site = 'https://' + Site.objects.get_current().domain
    receiver = recurring_payment.user

    # Compose the mail
    context = Context({'order': recurring_order,
                       'receiver_first_name': receiver.first_name.capitalize(),
                       'date': format_date(locale='nl_NL'),
                       'amount': format_currency(recurring_payment.amount / 100, 'EUR', locale='nl_NL'),
                       'site': site})
    subject = "Bedankt voor je maandelijkse 1%"
    text_content = get_template('monthly_donation.mail.txt').render(context)
    html_content = get_template('monthly_donation.mail.html').render(context)
    msg = EmailMultiAlternatives(subject=subject, body=text_content, to=[receiver.email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()
