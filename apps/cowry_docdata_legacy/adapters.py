# coding=utf-8
import logging
from docdata.interface import PaymentInterface
from django.conf import settings
from apps.cowry.adapters import AbstractPaymentAdapter
from apps.cowry.models import PaymentStatuses, PaymentLogLevels
from apps.cowry_docdata.adapters import log_status_update, log_status_change
from apps.cowry_docdata.models import DocDataPayment

logger = logging.getLogger(__name__)


class DocdataLegacyPaymentAdapter(AbstractPaymentAdapter):
    # Mapping of DocData legacy statuses to Cowry statuses.
    status_mapping = {
        'new': PaymentStatuses.new,
        'started': PaymentStatuses.in_progress,
        'authorized': PaymentStatuses.pending,
        'authorization_requested': PaymentStatuses.pending,
        'paid': PaymentStatuses.pending,
        'canceled': PaymentStatuses.cancelled,
        'charged-back': PaymentStatuses.cancelled,
        'confirmed_paid': PaymentStatuses.paid,
        'confirmed_chargedback': PaymentStatuses.cancelled,
        'closed_success': PaymentStatuses.paid,
        'closed_canceled': PaymentStatuses.cancelled,
    }

    def __init__(self, *args, **kwargs):
        super(DocdataLegacyPaymentAdapter, self).__init__()
        self.payment_interface = PaymentInterface(debug=False)
        self.merchant_name = getattr(settings, "COWRY_DOCDATA_LEGACY_MERCHANT_NAME", None)
        self.merchant_password = getattr(settings, "COWRY_DOCDATA_LEGACY_LIVE_MERCHANT_PASSWORD", None)

    def update_payment_status(self, payment, status_changed_notification=False):
        # We can't do anything if DocData Legacy credentials aren't available.
        if not self.merchant_name or not self.merchant_password:
            logger.error("DocData Legacy credentials aren't set. Can't update payment status.")
            return

        # Don't do anything if there's no payment or payment_order_id.
        if not payment or not payment.payment_order_id:
            return

        if payment.payment_method_id != 'legacy':
            logger.warn("Ignoring attempt to update legacy status using non-legacy payment: {0}".format(payment.payment_order_id))
            return

        # Execute status request.
        status_report = self.payment_interface.status_payment_cluster(merchant_name=self.merchant_name,
                                                                      merchant_password=self.merchant_password,
                                                                      payment_cluster_key=payment.payment_order_id,
                                                                      report_type='xml_std')

        # Example status replies:
        #
        # {u'cluster_amount': u'20.00',
        #  u'cluster_currency': u'EUR',
        #  u'last_partial_payment_method': u'ideal-ing-1procentclub_nl',
        #  u'last_partial_payment_process': u'paid',
        #  u'meta_amount_received': u'paid',
        #  u'meta_charged_back': u'N',
        #  u'meta_considered_safe': u'true',
        #  u'payment_cluster_process': u'closed_success',
        #  u'payout_process': u'started'}
        #
        # {u'cluster_amount': u'40.00',
        #  u'cluster_currency': u'EUR',
        #  u'last_partial_payment_method': u'ing-ideal-1procentclub_nl',
        #  u'last_partial_payment_process': u'canceled',
        #  u'meta_amount_received': u'none',
        #  u'meta_charged_back': u'N',
        #  u'meta_considered_safe': u'false',
        #  u'payment_cluster_process': u'started',
        #  u'payout_process': u'new'}

        if not status_report and status_changed_notification:
            log_status_update(payment, PaymentLogLevels.warn,
                              "Status changed notification received but status report was empty.")
            return

        # Find or create the DocDataPayment for current report.
        try:
            ddpayment = DocDataPayment.objects.get(docdata_payment_order=payment)
        except DocDataPayment.DoesNotExist:
            # New object created when it doesn't exist.
            ddpayment = DocDataPayment()
            ddpayment.docdata_payment_order = payment

        # Save some information from the report.
        ddpayment.payment_method = status_report['last_partial_payment_method']
        ddpayment.save()

        if not status_report['last_partial_payment_process'] in self.status_mapping:
            # Note: We continue to process the payment status change on this error.
            log_status_update(payment, PaymentLogLevels.error,
                              "Received unknown payment status from DocData: {0}".format(status_report['last_partial_payment_process']))

        # Update the DocDataPayment status.
        if ddpayment.status != status_report['last_partial_payment_process']:
            log_status_change(payment, PaymentLogLevels.info, "DocData Payment: {0} -> {1}".format(ddpayment.status,
                                                                                                  status_report['last_partial_payment_process']))
            ddpayment.status = status_report['last_partial_payment_process']
            ddpayment.save()

        old_status = payment.status
        new_status = self._map_status(ddpayment.status, payment, status_report)

        # TODO: Move this logging to AbstractPaymentAdapter when PaymentLogEntry is not abstract.
        if old_status != new_status:
            if new_status not in PaymentStatuses.values:
                log_status_change(payment, PaymentLogLevels.warn,
                                  "Payment {0} -> {1}".format(old_status, PaymentStatuses.unknown))
            else:
                log_status_change(payment, PaymentLogLevels.info,
                                  "Payment {0} -> {1}".format(old_status, new_status))

        self._change_status(payment, new_status)  # Note: change_status calls payment.save().

        # TODO # Set the payment fee.
        # docdata_fees = getattr(settings, 'COWRY_DOCDATA_LEGACY_FEES', None)
        # if docdata_fees:
        #     if ddpayment.payment_method in docdata_fees:
        #         payment_cost_setting = str(docdata_fees[ddpayment.payment_method])
        #         if '%' in payment_cost_setting:
        #             # Note: This assumes that the amount in the payment method will cover the full cost of the
        #             # payment order. It seems that DocData allows multiple payments to make up the full order
        #             # total. The method used here should be ok for 1%CLUB but it may not be suitable for others.
        #             cost_percent = Decimal(payment_cost_setting.replace('%', '')) / 100
        #             payment_cost = cost_percent * payment.amount
        #         else:
        #             payment_cost = Decimal(payment_cost_setting) * 100
        #
        #         payment.fee = payment_cost.quantize(Decimal('1.'), rounding=ROUND_HALF_UP) + 20
        #         payment.save()
        #
        #     else:
        #         log_status_update(payment, PaymentLogLevels.warn,
        #                           "Can't set payment fee for {0} because payment method is not in COWRY_DOCDATA_LEGACY_FEES.".format(
        #                           ddpayment.payment_id))
        # else:
        #     log_status_update(payment, PaymentLogLevels.warn,
        #                       "Can't set payment fee for {0} because COWRY_DOCDATA_LEGACY_FEES is not in set.".format(
        #                           ddpayment.payment_id))

    def _map_status(self, status, payment=None, status_report=None):
        new_status = super(DocdataLegacyPaymentAdapter, self)._map_status(status)

        # Status mapping override.
        if status_report[u'meta_considered_safe'] == u'true':
            log_status_update(payment, PaymentLogLevels.info, "meta_considered_safe = true")
            new_status = PaymentStatuses.paid

        return new_status
