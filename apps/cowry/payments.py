from .factory import _adapter_for_payment_method


def create_remote_payment_order(payment):
    adapter = _adapter_for_payment_method(payment.payment_method_id)
    adapter.create_remote_payment_order(payment)

def update_payment_object(payment, **kwargs):
    adapter = _adapter_for_payment_method(payment.payment_method_id)
    adapter.update_payment_object(payment, **kwargs)

def update_payment_status(payment, status_changed_notification=False):
    adapter = _adapter_for_payment_method(payment.payment_method_id)
    return adapter.update_payment_status(payment, status_changed_notification)

def get_webmenu_payment_url(payment):
    adapter = _adapter_for_payment_method(payment.payment_method_id)
    return adapter.get_webmenu_payment_url(payment)

def cancel_payment(payment):
    raise NotImplementedError

def refund_payment(payment):
    raise NotImplementedError
