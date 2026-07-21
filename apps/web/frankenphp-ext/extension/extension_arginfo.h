/* Hand-written arginfo for the maagap extension (kept in sync with
 * extension.stub.php). */

ZEND_BEGIN_ARG_WITH_RETURN_TYPE_INFO_EX(arginfo_maagap_fingerprint, 0, 1, IS_STRING, 0)
	ZEND_ARG_TYPE_INFO(0, data, IS_STRING, 0)
ZEND_END_ARG_INFO()

ZEND_FUNCTION(maagap_fingerprint);

static const zend_function_entry ext_functions[] = {
	ZEND_FE(maagap_fingerprint, arginfo_maagap_fingerprint)
	ZEND_FE_END
};
