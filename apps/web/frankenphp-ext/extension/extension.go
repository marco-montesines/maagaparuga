// Package extension implements the maagap FrankenPHP extension — PHP
// functions written in Go (the PHP-functions-in-Go showcase bridge,
// mirroring the haveibeenpwned frankenphp/ convention).
//
// It provides the PHP function:
//
//	maagap_fingerprint(string $data): string
//
// which returns the xxHash3-128 content fingerprint as lowercase hex —
// byte-identical to PHP's hash('xxh128', $data) fallback, so document ids
// stay stable whether or not the extension is compiled in.
//
// It must be compiled into FrankenPHP with xcaddy — see apps/web/Dockerfile
// (--target with-extension).
package extension

// #cgo CFLAGS: -D_GNU_SOURCE
// #include "extension.h"
import "C"

import (
	"fmt"
	"unsafe"

	"github.com/dunglas/frankenphp"
	"github.com/zeebo/xxh3"
)

func init() {
	frankenphp.RegisterExtension(unsafe.Pointer(&C.maagap_module_entry))
}

// maagap_fingerprint returns the xxHash3-128 fingerprint of data as
// lowercase hex (canonical big-endian, matching PHP's hash('xxh128', ...)).
//
//export maagap_fingerprint
func maagap_fingerprint(data *C.zend_string) *C.zend_string {
	sum := xxh3.Hash128([]byte(frankenphp.GoString(unsafe.Pointer(data))))
	hex := fmt.Sprintf("%016x%016x", sum.Hi, sum.Lo)

	return (*C.zend_string)(frankenphp.PHPString(hex, false))
}
