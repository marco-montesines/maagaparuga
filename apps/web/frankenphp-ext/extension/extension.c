/* C bridge between the Zend engine and the Go implementation in
 * extension.go. The Go symbols are provided by cgo via _cgo_export.h. */

#include <php.h>
#include "extension.h"
#include "extension_arginfo.h"
#include "_cgo_export.h"

PHP_FUNCTION(maagap_fingerprint)
{
	zend_string *data;

	ZEND_PARSE_PARAMETERS_START(1, 1)
		Z_PARAM_STR(data)
	ZEND_PARSE_PARAMETERS_END();

	RETURN_STR(maagap_fingerprint(data));
}

zend_module_entry maagap_module_entry = {
	STANDARD_MODULE_HEADER,
	"maagap",
	ext_functions,
	NULL, /* MINIT */
	NULL, /* MSHUTDOWN */
	NULL, /* RINIT */
	NULL, /* RSHUTDOWN */
	NULL, /* MINFO */
	"1.0.0",
	STANDARD_MODULE_PROPERTIES
};
