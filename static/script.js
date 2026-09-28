document.addEventListener('DOMContentLoaded', () => {
    // Only run if we are on the index page
    const productsBody = document.getElementById('productsBody');
    if (!productsBody) return;

    const grandTotalElement = document.getElementById('grandTotal');
    const generateBtn = document.getElementById('generateBtn');
    const customerNameInput = document.getElementById('customerName');
    const loadingOverlay = document.getElementById('loadingOverlay');
    
    const breadSelect = document.getElementById('breadSelect');
    const addBreadBtn = document.getElementById('addBreadBtn');
    const emptyState = document.getElementById('emptyState');
    const productsTable = document.getElementById('productsTable');

    // Add selected bread to table
    addBreadBtn.addEventListener('click', () => {
        const breadType = breadSelect.value;
        if (!breadType) return;

        // Check if already in table
        const existingRow = productsBody.querySelector(`tr[data-bread="${breadType}"]`);
        if (existingRow) {
            alert('Este pan ya fue agregado a la lista. Puedes modificar su cantidad.');
            return;
        }

        // Get saved price
        const price = BREAD_PRICES[breadType] || 0;
        const priceStr = price > 0 ? price : '';

        const tr = document.createElement('tr');
        tr.className = 'product-row';
        tr.dataset.bread = breadType;
        
        tr.innerHTML = `
            <td class="bread-name" data-label="Tipo de Pan">${breadType}</td>
            <td data-label="Cantidad">
                <div class="qty-control">
                    <button type="button" class="qty-btn minus" tabindex="-1"><i class="fa-solid fa-minus"></i></button>
                    <input type="number" class="qty-input" min="0" value="0" aria-label="Cantidad">
                    <button type="button" class="qty-btn plus" tabindex="-1"><i class="fa-solid fa-plus"></i></button>
                </div>
            </td>
            <td data-label="Precio Unit. ($)">
                <input type="number" class="price-input" min="0" step="0.01" value="${priceStr}" placeholder="0.00" aria-label="Precio Unitario">
            </td>
            <td class="subtotal-cell" data-label="Subtotal ($)">0.00</td>
            <td class="action-cell">
                <button type="button" class="btn-delete" title="Quitar producto"><i class="fa-solid fa-trash"></i></button>
            </td>
        `;

        productsBody.appendChild(tr);
        
        // Reset select
        breadSelect.value = '';
        
        // Update UI
        updateTableVisibility();
        calculateRowSubtotal(tr);
        calculateGrandTotal();
    });

    function updateTableVisibility() {
        const hasRows = productsBody.children.length > 0;
        if (hasRows) {
            emptyState.classList.add('hidden');
            productsTable.style.display = 'table'; // or block for mobile via CSS
            generateBtn.disabled = false;
        } else {
            emptyState.classList.remove('hidden');
            productsTable.style.display = 'none';
            generateBtn.disabled = true;
        }
    }

    // Initialize visibility
    updateTableVisibility();

    // Event Delegation for Delete and Plus/Minus buttons
    productsTable.addEventListener('click', (e) => {
        // Handle Delete
        if (e.target.closest('.btn-delete')) {
            const row = e.target.closest('tr');
            row.remove();
            updateTableVisibility();
            calculateGrandTotal();
            return;
        }

        // Handle Plus/Minus
        if (e.target.closest('.qty-btn')) {
            const btn = e.target.closest('.qty-btn');
            const row = btn.closest('tr');
            const input = row.querySelector('.qty-input');
            let val = parseInt(input.value) || 0;
            
            if (btn.classList.contains('plus')) {
                val += 1;
            } else if (btn.classList.contains('minus')) {
                val = val > 0 ? val - 1 : 0; // Minimum 0
            }
            
            input.value = val;
            
            calculateRowSubtotal(row);
            calculateGrandTotal();
        }
    });

    // Input changes
    productsTable.addEventListener('input', (e) => {
        if (e.target.classList.contains('qty-input') || e.target.classList.contains('price-input')) {
            const row = e.target.closest('tr');
            calculateRowSubtotal(row);
            calculateGrandTotal();
        }
    });

    function calculateRowSubtotal(row) {
        const qtyInput = row.querySelector('.qty-input');
        const priceInput = row.querySelector('.price-input');
        const subtotalCell = row.querySelector('.subtotal-cell');

        const qty = parseFloat(qtyInput.value) || 0;
        const price = parseFloat(priceInput.value) || 0;
        const subtotal = qty * price;

        subtotalCell.textContent = subtotal.toFixed(2);
        
        if (qty > 0 && price > 0) {
            row.style.borderLeft = '4px solid var(--primary-color)';
        } else {
            row.style.borderLeft = '';
        }
    }

    function calculateGrandTotal() {
        const rows = document.querySelectorAll('.product-row');
        let total = 0;

        rows.forEach(row => {
            const subtotalText = row.querySelector('.subtotal-cell').textContent;
            total += parseFloat(subtotalText) || 0;
        });

        grandTotalElement.textContent = `$${total.toFixed(2)}`;
    }

    generateBtn.addEventListener('click', async () => {
        const rows = document.querySelectorAll('.product-row');
        const items = [];
        let hasError = false;

        rows.forEach(row => {
            const qty = parseFloat(row.querySelector('.qty-input').value) || 0;
            const price = parseFloat(row.querySelector('.price-input').value) || 0;
            
            if (qty > 0 && price > 0) {
                const breadType = row.dataset.bread;
                items.push({
                    bread_type: breadType,
                    quantity: qty,
                    unit_price: price,
                    total_price: qty * price
                });
            } else {
                hasError = true;
            }
        });

        if (hasError) {
            alert('Asegúrese de que todos los productos agregados tengan una cantidad y precio válidos mayores a 0.');
            return;
        }

        if (items.length === 0) {
            alert('Por favor, agregue al menos un producto a la factura.');
            return;
        }

        const customerName = customerNameInput.value.trim() || 'Consumidor Final';

        loadingOverlay.classList.remove('hidden');

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    customer_name: customerName,
                    items: items
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Error al generar la factura');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            
            const disposition = response.headers.get('Content-Disposition');
            let filename = 'factura.png';
            if (disposition && disposition.indexOf('attachment') !== -1) {
                var filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                var matches = filenameRegex.exec(disposition);
                if (matches != null && matches[1]) { 
                    filename = matches[1].replace(/['"]/g, '');
                }
            }

            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            // Optional: clear table after successful generation
            productsBody.innerHTML = '';
            updateTableVisibility();
            calculateGrandTotal();
            customerNameInput.value = '';

        } catch (error) {
            alert('Error: ' + error.message);
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    });
});
